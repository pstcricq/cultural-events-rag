"""The assistant served: the configuration chosen by the evaluation of the
search, its reranker run only when chosen and the environment can run it,
its pieces loaded from the settings, a question searched then answered."""

from datetime import date
from typing import Any

import pytest

from cultural_events_rag.assistant import (
    RERANK,
    SEARCH_MODE,
    Assistant,
    load_assistant,
    reranker_model,
)
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.retrieval.rerank import RERANK_MODEL
from cultural_events_rag.retrieval.search import SEARCH_K
from cultural_events_rag.settings import Settings


def test_the_best_configuration_of_the_evaluation_is_served() -> None:
    assert (SEARCH_MODE, RERANK) == ("hybrid", True)


@pytest.mark.parametrize(
    ("rerank", "available", "model"),
    [(True, True, RERANK_MODEL), (True, False, None), (False, True, None)],
)
def test_the_reranker_runs_when_chosen_and_available(
    rerank: bool,
    available: bool,
    model: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cultural_events_rag.assistant.RERANK", rerank)
    settings = Settings(_env_file=None, rerank_available=available)

    assert reranker_model(settings) == model


def test_the_reranker_chosen_needs_rerank_available() -> None:
    with pytest.raises(MissingSettingError, match="RERANK_AVAILABLE"):
        reranker_model(Settings(_env_file=None))


def test_the_assistant_loaded_from_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prefix = "cultural_events_rag.assistant"
    monkeypatch.setattr(f"{prefix}.make_elastic_client", lambda _: "client")
    monkeypatch.setattr(f"{prefix}.make_embeddings", lambda _: "embeddings")
    monkeypatch.setattr(f"{prefix}.make_chat_model", lambda settings, pacer: pacer)
    monkeypatch.setattr(f"{prefix}.recommender", lambda llm: llm)
    settings = Settings(
        _env_file=None,
        elasticsearch_index="events",
        rerank_available=True,
        llm_requests_per_minute=6,
    )

    def load(model: str) -> Any:
        return f"reranker {model}"

    assistant: Any = load_assistant(settings, load_reranker=load)  # made of fakes

    assert (assistant.client, assistant.index) == ("client", "events")
    assert assistant.embeddings == "embeddings"
    assert assistant.reranker == f"reranker {RERANK_MODEL}"
    assert assistant.model.interval == 10.0  # its quota: one call every 10 s
    assert load_assistant(settings, rerank=False).reranker is None
    monkeypatch.setattr(f"{prefix}.SEARCH_MODE", "lexical")
    assert load_assistant(settings, rerank=False).embeddings is None


def test_a_question_is_searched_as_chosen_then_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def retrieve(*args: Any) -> str:
        calls.append(args)
        return "events found"

    monkeypatch.setattr("cultural_events_rag.assistant.retrieve", retrieve)
    monkeypatch.setattr(
        "cultural_events_rag.assistant.generate",
        lambda model, question, today, retrieval: f"answer from {retrieval}",
    )
    assistant = Assistant("client", "an-alias", "vectors", "reranker", "llm")  # type: ignore[arg-type]
    today = date(2026, 10, 19)

    assert assistant.ask("Un concert ?", today) == "answer from events found"  # type: ignore[comparison-overlap]
    assert calls == [
        (
            "client",
            "an-alias",
            "Un concert ?",
            today,
            SEARCH_MODE,
            SEARCH_K,
            "vectors",
            "reranker",
        )
    ]
