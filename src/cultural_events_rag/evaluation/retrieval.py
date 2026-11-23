"""The evaluation of the search: each question of the benchmark searched in its
index as of its reference date, by each configuration, and the events found
compared with those judged relevant.

The metrics, for the questions with relevant events:

- Hit@k: 1 when a relevant event is in the first k.
- Recall@k: the relevant events in the first k, out of min(k, relevant
  events).
- Precision@k: the share of the first k that is relevant.
- MRR: the mean of 1 / the rank of the first relevant event, 0 without
  one."""

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

# The events the assistant shows, and the candidates of the reranker.
SHOWN, CANDIDATES = SEARCH_K, RERANK_CANDIDATES


@dataclass(frozen=True)
class RetrievalConfig:
    """A search configuration: a mode, with or without the reranker."""

    mode: SearchMode
    rerank: bool

    @property
    def name(self) -> str:
        return f"{self.mode} + rerank" if self.rerank else self.mode


# The configurations compared: the three modes, without then with the reranker.
CONFIGS = tuple(
    RetrievalConfig(mode, rerank)
    for rerank in (False, True)
    for mode in ("lexical", "vector", "hybrid")
)


def hit_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return float(any(uid in relevant for uid in ranked[:k]))


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Return Recall@k, capped at min(k, relevant events)."""
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
    scores: list[float]  # BM25, cosine, RRF or the reranker's, after the configuration
    filters: str  # those the analysis found, see added_filters

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
        """Return the metrics of a question with relevant events."""
        ranked, relevant = self.ranked, self.relevant
        return {
            f"hit@{SHOWN}": hit_at_k(ranked, relevant, SHOWN),
            f"recall@{SHOWN}": recall_at_k(ranked, relevant, SHOWN),
            f"precision@{SHOWN}": precision_at_k(ranked, relevant, SHOWN),
            "mrr": reciprocal_rank(ranked, relevant),
            f"recall@{CANDIDATES}": recall_at_k(ranked, relevant, CANDIDATES),
        }


def in_scope(results: Sequence[QuestionResult]) -> list[QuestionResult]:
    """Return the results of the questions with relevant events."""
    return [result for result in results if result.relevant]


def summary(results: Sequence[QuestionResult]) -> dict[str, float]:
    """Return the metrics averaged over the questions with relevant events."""
    scored = [result.metrics() for result in in_scope(results)]
    return {name: mean(metrics[name] for metrics in scored) for name in scored[0]}


def wins(
    results: Sequence[QuestionResult],
    other: Sequence[QuestionResult],
    metric: str = f"recall@{SHOWN}",
) -> int:
    """Return the questions where ``results`` does better than ``other`` on
    ``metric``."""
    return sum(
        result.metrics()[metric] > theirs.metrics()[metric]
        for result, theirs in zip(in_scope(results), in_scope(other), strict=True)
    )


def added_filters(filters: SearchFilters, reference_date: date) -> str:
    """Return the filters the analysis found in a question, besides the start
    at the reference date every search has; "-" when none."""
    if filters.date_from == reference_date and filters.date_to is None:
        filters = filters.model_copy(update={"date_from": None})
    described = filters.describe()
    return "-" if described == "none" else described


class CachedEmbeddings(Embeddings):
    """Embeddings that compute the vector of each question once."""

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
    """Search each question of ``dataset`` in ``index`` with ``config`` as of
    its reference date: the first CANDIDATES events, reranked all together with
    the reranker."""
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
