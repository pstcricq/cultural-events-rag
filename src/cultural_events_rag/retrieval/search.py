"""The search of the events a question asks for, in the index served.

1. The question is analyzed into filters (``query_analysis``), translated into
   the filter clauses of each query (``filter_clauses``).
2. Lexical: the question matched with the French text of the entries (BM25).
   Vector: its vector compared with theirs, by cosine (exact kNN). Hybrid:
   both, their rankings fused by Reciprocal Rank Fusion (RRF), in Python (the
   RRF of Elasticsearch needs a paid licence).
3. The entries are chunks: each list is grouped by event, an event at the rank
   of its best chunk, before the fusion and the top ``k``.
4. Optionally, a reranker sorts the first candidates again (``rerank``).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from tenacity import Retrying

from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.elastic import index_alias
from cultural_events_rag.indexing.build import index_signature
from cultural_events_rag.indexing.store import served_index, signature_differences
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.query_analysis import PlaceMatcher, analyze
from cultural_events_rag.retrieval.rerank import Reranker, rerank
from cultural_events_rag.retry import make_retrying
from cultural_events_rag.settings import Settings

# How the events of a question can be searched: by the words of their text
# (BM25), by the meaning of their vector (kNN), or both, fused. The assistant
# picks one (assistant.py).
SearchMode = Literal["lexical", "vector", "hybrid"]
# The events kept, given to the LLM and shown.
SEARCH_K = 5

# The entries each search ranks, before they are grouped by event: enough for
# the k events even when they have several chunks each.
CANDIDATES = 50
# The constant of RRF, that of its paper and of Elasticsearch: the larger, the
# less the first ranks weigh against the next ones.
RRF_K = 60
# The events of the search a reranker sorts again: the cost of the reranking
# grows with them, one pass of its model per event.
RERANK_CANDIDATES = 20

Hit = dict[str, Any]


@dataclass(frozen=True)
class EventMatch:
    """An event found, its score, its best chunk and its rank in each list."""

    uid: str
    score: float  # BM25, cosine similarity or RRF, after the mode
    chunk: Document
    # "lexical", "vector", and "hybrid" after their fusion: absent from a
    # list, no rank.
    ranks: dict[str, int]


@dataclass(frozen=True)
class Retrieval:
    """The filters of a question, and the events found with them, best first."""

    filters: SearchFilters
    matches: list[EventMatch]


def index_problem(client: Elasticsearch, settings: Settings) -> str | None:
    """Why the index served cannot be searched: none behind the alias, or
    built otherwise than the code builds it now; None when it can."""
    alias = index_alias(settings)
    info = served_index(client, alias)
    if info is None:
        return f"no index behind {alias}: run make index"
    differences = signature_differences(info.meta, index_signature())
    if differences:
        return f"outdated index: {'; '.join(differences)}: run make index"
    return None


def filter_clauses(filters: SearchFilters) -> list[dict[str, Any]]:
    """The filter clauses of an Elasticsearch query: none without any
    constraint. Elasticsearch keeps the entries every clause accepts, then
    ranks only those."""
    clauses: list[dict[str, Any]] = []
    if filters.date_from or filters.date_to:
        # Days of the city: a slot from 23:30 to 01:00 is on both days.
        period: dict[str, Any] = {
            "relation": "intersects",
            "time_zone": TIMEZONE.key,
        }
        if filters.date_from:
            period["gte"] = filters.date_from.isoformat()
        if filters.date_to:
            period["lte"] = f"{filters.date_to.isoformat()}||/d"  # to its end
        clauses.append({"range": {"timings": period}})
    if filters.district:
        clauses.append({"term": {"district": filters.district}})
    if filters.venue:
        clauses.append({"match_phrase": {"venue.folded": filters.venue}})
    if filters.free:
        # Free, or a price the agenda does not give: many free events do not
        # say so. Only the paid ones are left out; the answer tells which
        # price is unknown.
        unknown = {"bool": {"must_not": {"exists": {"field": "is_free"}}}}
        clauses.append(
            {
                "bool": {
                    "should": [{"term": {"is_free": True}}, unknown],
                    "minimum_should_match": 1,
                }
            }
        )
    return clauses


def lexical_hits(
    client: Elasticsearch,
    index: str,
    question: str,
    clauses: list[dict[str, Any]],
    size: int = CANDIDATES,
) -> list[Hit]:
    """The entries the filters keep, ranked by BM25 on their French text."""
    query = {"bool": {"must": [{"match": {"text": question}}], "filter": clauses}}
    response = client.search(
        index=index, size=size, query=query, source_excludes=["vector"]
    )
    hits: list[Hit] = response["hits"]["hits"]
    return hits


def vector_hits(
    client: Elasticsearch,
    index: str,
    vector: list[float],
    clauses: list[dict[str, Any]],
    size: int = CANDIDATES,
) -> list[Hit]:
    """The entries the filters keep, ranked by the cosine of their vector with
    ``vector``: every one compared (flat index)."""
    knn = {
        "field": "vector",
        "query_vector": vector,
        "k": size,
        "num_candidates": size,
        "filter": clauses,
    }
    response = client.search(
        index=index, size=size, knn=knn, source_excludes=["vector"]
    )
    hits: list[Hit] = response["hits"]["hits"]
    return hits


def by_event(hits: Sequence[Hit]) -> dict[str, Hit]:
    """The events of a ranking of entries, in its order, each with its best
    entry: the next ones are skipped."""
    best: dict[str, Hit] = {}
    for hit in hits:
        best.setdefault(hit["_source"]["uid"], hit)
    return best


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> dict[str, float]:
    """The RRF score of each item: the sum, over the rankings it is in, of
    1 / (k + its rank)."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1 / (k + rank)
    return dict(scores)


def to_document(hit: Hit) -> Document:
    """An entry as a document: its text, and the rest of what it stores."""
    metadata = dict(hit["_source"])
    return Document(id=hit["_id"], page_content=metadata.pop("text"), metadata=metadata)


def search_events(
    client: Elasticsearch,
    index: str,
    question: str,
    vector: list[float] | None,
    filters: SearchFilters,
    mode: SearchMode,
    k: int,
) -> list[EventMatch]:
    """The ``k`` events of ``index`` closest to ``question`` among those the
    filters keep, best first; ``vector`` is the one of the question, unused by
    the lexical search."""
    clauses = filter_clauses(filters)
    lists: dict[str, dict[str, Hit]] = {}
    if mode in ("lexical", "hybrid"):
        lists["lexical"] = by_event(lexical_hits(client, index, question, clauses))
    if mode in ("vector", "hybrid"):
        if vector is None:
            raise ValueError(f"the {mode} search needs the vector of the question")
        lists["vector"] = by_event(vector_hits(client, index, vector, clauses))

    ranks: dict[str, dict[str, int]] = defaultdict(dict)
    best: dict[str, tuple[int, Hit]] = {}  # the hit of its best rank, by uid
    for name, events in lists.items():
        for rank, (uid, hit) in enumerate(events.items(), 1):
            ranks[uid][name] = rank
            if uid not in best or rank < best[uid][0]:
                best[uid] = (rank, hit)

    if mode == "hybrid":
        scores = rrf([list(events) for events in lists.values()])
    else:
        [events] = lists.values()
        scores = {uid: hit["_score"] for uid, hit in events.items()}
    top = sorted(scores, key=lambda uid: scores[uid], reverse=True)[:k]
    if mode == "hybrid":
        for rank, uid in enumerate(top, 1):
            ranks[uid]["hybrid"] = rank
    return [
        EventMatch(
            uid=uid,
            score=scores[uid],
            chunk=to_document(best[uid][1]),
            ranks=ranks[uid],
        )
        for uid in top
    ]


def retrieve(
    client: Elasticsearch,
    index: str,
    question: str,
    today: date,
    mode: SearchMode,
    k: int,
    embeddings: Embeddings | None = None,
    reranker: Reranker | None = None,
    candidates: int = RERANK_CANDIDATES,
    retrying: Retrying | None = None,
) -> Retrieval:
    """The filters of ``question`` asked on ``today``, and the ``k`` events of
    ``index`` they keep that are closest to it; ``embeddings`` turns the
    question into a vector, unused by the lexical search. With ``reranker``,
    the first ``candidates`` events of the search are sorted again by it."""
    filters = analyze(question, today, PlaceMatcher.from_index(client, index))
    vector = None
    if mode != "lexical":
        if embeddings is None:
            raise ValueError(f"the {mode} search needs an embedding model")
        retrying = retrying or make_retrying("Embedding")
        vector = retrying(embeddings.embed_query, question)
    size = max(candidates, k) if reranker else k
    matches = search_events(client, index, question, vector, filters, mode, size)
    if reranker:
        matches = rerank(reranker, question, matches, k)
    return Retrieval(filters=filters, matches=matches)


def first_slot(match: EventMatch, filters: SearchFilters) -> datetime:
    """The first slot of the event the period of the filters keeps, in the time
    of the city: a series can have started long before."""
    slots = [
        (
            datetime.fromisoformat(slot["gte"]).astimezone(TIMEZONE),
            datetime.fromisoformat(slot["lte"]).astimezone(TIMEZONE),
        )
        for slot in match.chunk.metadata["timings"]  # as the index stores them
    ]
    for begin, end in slots:
        after = filters.date_from is None or end.date() >= filters.date_from
        before = filters.date_to is None or begin.date() <= filters.date_to
        if after and before:
            return begin
    return slots[0][0]
