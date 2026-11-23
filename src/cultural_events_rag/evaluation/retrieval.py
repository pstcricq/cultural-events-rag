"""The evaluation of the search: each question of the benchmark searched in its
index, as of its reference date, by each configuration, and the events found
compared with those judged relevant. No LLM: the same run gives the same
numbers.

The metrics, on the ranking of events, for the questions with relevant events
(out-of-scope ones show only what comes first for them):

- Hit@k: 1 when a relevant event is in the first k.
- Recall@k: the relevant events in the first k, out of min(k, relevant
  events): with 200 events relevant to "en décembre", five relevant events
  in the first five is a perfect answer (1.0), not 5 / 200.
- Precision@k: the share of the first k that is relevant.
- MRR: the mean of 1 / the rank of the first relevant event, 0 without one.

k = 5 is what the assistant shows, k = 20 the candidates of the reranker:
the reranker can only bring up an event among them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import mean

from elasticsearch import Elasticsearch
from langchain_core.embeddings import Embeddings

from cultural_events_rag.evaluation.dataset import EvalDataset, EvalQuestion
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.rerank import Reranker
from cultural_events_rag.retrieval.search import (
    RERANK_CANDIDATES,
    SEARCH_K,
    SearchMode,
    retrieve,
)

# The events the assistant shows, and the candidates of the reranker: those of
# the search itself, so that the evaluation measures what the assistant serves.
SHOWN, CANDIDATES = SEARCH_K, RERANK_CANDIDATES


@dataclass(frozen=True)
class RetrievalConfig:
    """How the events are searched: a mode, with or without the reranker."""

    mode: SearchMode
    rerank: bool

    @property
    def name(self) -> str:
        return f"{self.mode} + rerank" if self.rerank else self.mode


# Every configuration compared: the three modes, without then with the reranker.
CONFIGS = tuple(
    RetrievalConfig(mode, rerank)
    for rerank in (False, True)
    for mode in ("lexical", "vector", "hybrid")
)


def hit_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return float(any(uid in relevant for uid in ranked[:k]))


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Capped at min(k, relevant events): see the module."""
    return len(relevant.intersection(ranked[:k])) / min(k, len(relevant))


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return len(relevant.intersection(ranked[:k])) / k


def reciprocal_rank(ranked: Sequence[str], relevant: set[str]) -> float:
    return next(
        (1 / rank for rank, uid in enumerate(ranked, 1) if uid in relevant), 0.0
    )


@dataclass(frozen=True)
class QuestionResult:
    """The events a configuration found for a question, best first."""

    question: EvalQuestion
    ranked: list[str]  # uids
    titles: list[str]
    scores: list[float]  # BM25, cosine, RRF or the reranker's, after the config
    filters: str  # those the analysis found: see added_filters

    @property
    def relevant(self) -> set[str]:
        return set(self.question.relevant)

    @property
    def first_relevant_rank(self) -> int | None:
        return next(
            (rank for rank, uid in enumerate(self.ranked, 1) if uid in self.relevant),
            None,
        )

    def metrics(self) -> dict[str, float]:
        """Its metrics: for a question with relevant events only."""
        ranked, relevant = self.ranked, self.relevant
        return {
            f"hit@{SHOWN}": hit_at_k(ranked, relevant, SHOWN),
            f"recall@{SHOWN}": recall_at_k(ranked, relevant, SHOWN),
            f"precision@{SHOWN}": precision_at_k(ranked, relevant, SHOWN),
            "mrr": reciprocal_rank(ranked, relevant),
            f"recall@{CANDIDATES}": recall_at_k(ranked, relevant, CANDIDATES),
        }


def in_scope(results: Sequence[QuestionResult]) -> list[QuestionResult]:
    """The results of the questions with relevant events."""
    return [result for result in results if result.relevant]


def summary(results: Sequence[QuestionResult]) -> dict[str, float]:
    """The metrics averaged over the questions with relevant events."""
    scored = [result.metrics() for result in in_scope(results)]
    return {name: mean(metrics[name] for metrics in scored) for name in scored[0]}


def wins(
    results: Sequence[QuestionResult],
    other: Sequence[QuestionResult],
    metric: str = f"recall@{SHOWN}",
) -> int:
    """The questions where ``results`` does better than ``other`` on
    ``metric``: a mean can hide a few large gains or losses."""
    return sum(
        result.metrics()[metric] > theirs.metrics()[metric]
        for result, theirs in zip(in_scope(results), in_scope(other), strict=True)
    )


def added_filters(filters: SearchFilters, reference_date: date) -> str:
    """The filters the analysis found in a question, without the events from
    the reference date on that every search keeps by default: "-" when it
    found none."""
    if filters.date_from == reference_date and filters.date_to is None:
        filters = filters.model_copy(update={"date_from": None})
    described = filters.describe()
    return "-" if described == "none" else described


class CachedEmbeddings(Embeddings):
    """The vector of each question asked once, whatever the configurations
    that search it."""

    def __init__(self, embeddings: Embeddings) -> None:
        self.embeddings = embeddings
        self.vectors: dict[str, list[float]] = {}

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        if text not in self.vectors:
            self.vectors[text] = self.embeddings.embed_query(text)
        return self.vectors[text]


def evaluate(
    client: Elasticsearch,
    index: str,
    dataset: EvalDataset,
    config: RetrievalConfig,
    embeddings: Embeddings | None,
    reranker: Reranker | None,
) -> list[QuestionResult]:
    """Each question of ``dataset`` searched in ``index`` by ``config``, as of
    its reference date: the first CANDIDATES events, reranked all together
    with the reranker."""
    results = []
    for question in dataset.questions:
        retrieval = retrieve(
            client,
            index,
            question.question,
            dataset.reference_date,
            config.mode,
            CANDIDATES,
            embeddings if config.mode != "lexical" else None,
            reranker if config.rerank else None,
            candidates=CANDIDATES,
        )
        results.append(
            QuestionResult(
                question=question,
                ranked=[match.uid for match in retrieval.matches],
                titles=[match.chunk.metadata["title"] for match in retrieval.matches],
                scores=[match.score for match in retrieval.matches],
                filters=added_filters(retrieval.filters, dataset.reference_date),
            )
        )
    return results
