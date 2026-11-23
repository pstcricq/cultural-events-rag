"""The assistant served, put together from the pieces of each step: the search
in the index, the reranker, the LLM that writes the answer.

The choices come from the evaluation of the search (make eval-retrieval,
reports/retrieval.md): the search offers every mode and the reranker, the
assistant picks the configuration that came first on the benchmark. The
commands that answer a question (make ask, the API, make eval-generation) load
it here, all alike.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from elasticsearch import Elasticsearch
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import Runnable

from cultural_events_rag.elastic import index_alias, make_elastic_client
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.generation.answer import Answer, generate, recommender
from cultural_events_rag.mistral import (
    Pacer,
    make_chat_model,
    make_embeddings,
    requests_per_minute,
)
from cultural_events_rag.retrieval.rerank import (
    RERANK_MODEL,
    CrossEncoderReranker,
    Reranker,
)
from cultural_events_rag.retrieval.search import (
    SEARCH_K,
    Retrieval,
    SearchMode,
    retrieve,
)
from cultural_events_rag.settings import Settings

# The best configuration of reports/retrieval.md: both rankings fused, then the
# first candidates sorted again by the reranker.
SEARCH_MODE: SearchMode = "hybrid"
RERANK = True


def reranker_model(settings: Settings) -> str | None:
    """The reranker the assistant runs: RERANK_MODEL when the assistant
    reranks (RERANK) and the environment can run it (RERANK_AVAILABLE), else
    None."""
    if not RERANK:
        return None
    if settings.rerank_available is None:
        raise MissingSettingError("RERANK_AVAILABLE is not set: add it to .env")
    return RERANK_MODEL if settings.rerank_available else None


@dataclass(frozen=True)
class Assistant:
    """The clients and models a question needs, loaded once."""

    client: Elasticsearch
    index: str  # the alias of the events searched
    embeddings: Embeddings | None  # None for a lexical search
    reranker: Reranker | None
    model: Runnable[Any, Any]  # a recommender

    def search(self, question: str, today: date) -> Retrieval:
        """The events of ``question`` asked on ``today``: its filters, then
        the SEARCH_K events closest to it, reranked when it reranks."""
        return retrieve(
            self.client,
            self.index,
            question,
            today,
            SEARCH_MODE,
            SEARCH_K,
            self.embeddings,
            self.reranker,
        )

    def answer(self, question: str, today: date, retrieval: Retrieval) -> Answer:
        """The answer the LLM writes from the events of ``retrieval``."""
        return generate(self.model, question, today, retrieval)

    def ask(self, question: str, today: date) -> Answer:
        """The events of ``question``, then the answer written from them."""
        return self.answer(question, today, self.search(question, today))


def load_assistant(
    settings: Settings,
    client: Elasticsearch | None = None,
    index: str | None = None,
    rerank: bool = True,
    pacer: Pacer | None = None,
    load_reranker: Callable[[str], Reranker] = CrossEncoderReranker,
) -> Assistant:
    """The assistant of the settings, searching ``index`` (the alias of the
    settings by default) through ``client``. Without ``rerank``, no reranker
    even where it could run. Its chat model keeps to the quota of the Mistral
    plan, through ``pacer`` when the quota is shared (with the judge)."""
    model = reranker_model(settings) if rerank else None
    return Assistant(
        client=client or make_elastic_client(settings),
        index=index or index_alias(settings),
        embeddings=None if SEARCH_MODE == "lexical" else make_embeddings(settings),
        reranker=load_reranker(model) if model else None,
        model=recommender(
            make_chat_model(settings, pacer or Pacer(requests_per_minute(settings)))
        ),
    )
