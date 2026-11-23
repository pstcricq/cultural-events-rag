"""The assistant: the search configuration, the reranker and the chat model,
loaded together for every command that answers a question."""

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

# Hybrid search, then the first candidates reranked.
SEARCH_MODE: SearchMode = "hybrid"
RERANK = True


def reranker_model(settings: Settings) -> str | None:
    """Return the name of the reranker model, or None when the assistant does
    not rerank or the machine cannot run it (``RERANK_AVAILABLE``)."""
    if not RERANK:
        return None
    if settings.rerank_available is None:
        raise MissingSettingError("RERANK_AVAILABLE is not set: add it to .env")
    return RERANK_MODEL if settings.rerank_available else None


@dataclass(frozen=True)
class Assistant:
    """The clients and models a question needs, loaded once."""

    client: Elasticsearch
    index: str  # alias of the index searched
    embeddings: Embeddings | None  # None for a lexical search
    reranker: Reranker | None
    model: Runnable[Any, Any]  # the chain that writes the answer

    def search(self, question: str, today: date) -> Retrieval:
        """Return the filters of ``question`` asked on ``today`` and the
        ``SEARCH_K`` events closest to it, reranked when a reranker is loaded."""
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
        """Return the answer the chat model writes from the events of ``retrieval``."""
        return generate(self.model, question, today, retrieval)

    def ask(self, question: str, today: date) -> Answer:
        """Search the events of ``question``, then write the answer from them."""
        return self.answer(question, today, self.search(question, today))


def load_assistant(
    settings: Settings,
    client: Elasticsearch | None = None,
    index: str | None = None,
    rerank: bool = True,
    pacer: Pacer | None = None,
    load_reranker: Callable[[str], Reranker] = CrossEncoderReranker,
) -> Assistant:
    """Load the assistant of ``settings``, searching ``index`` (the alias of
    the settings by default) through ``client``.

    ``rerank=False`` loads no reranker. The chat model is paced by ``pacer``
    when the quota is shared with another model."""
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
