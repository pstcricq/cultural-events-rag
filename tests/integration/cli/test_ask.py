"""cultural-events-rag ask end to end against a real Elasticsearch, with a
fake embedding model and a fake LLM: the answer, then the events it recommends
with the details of the index."""

from typing import Any

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import RunnableLambda

from cultural_events_rag.cli import main
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)


@pytest.fixture
def read(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """The event indexed, and what the fake LLM reads: it recommends every
    uid of its prompt, and one it was not given."""
    build_index(client, [event], FAKE, settings)
    prompts: list[str] = []

    def answer(prompt: PromptValue) -> dict[str, Any]:
        prompts.append(prompt.to_string())
        return {"answer": "Une **visite** pour vous.", "event_uids": [event.uid, "x"]}

    prefix = "cultural_events_rag.cli.ask"
    monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)
    assistant = "cultural_events_rag.assistant"
    monkeypatch.setattr(f"{assistant}.make_embeddings", lambda _: FAKE)
    monkeypatch.setattr(f"{assistant}.make_chat_model", lambda *_: None)
    monkeypatch.setattr(f"{assistant}.recommender", lambda _: RunnableLambda(answer))
    return prompts


def test_ask_prints_the_answer_and_the_events_it_recommends(
    read: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    question = "Une visite guidée au musée des Augustins en juin ?"

    assert main(["ask", question, "--today", "2026-06-01"]) == 0

    out = capsys.readouterr().out
    assert "Filters: dates: 2026-06-01 to 2026-06-30, venue: Augustins" in out
    assert "\nUne visite pour vous.\n" in out
    assert "Events recommended: 1 of the 1 found" in out
    assert ' 1. Visite guidée "Les peintres caravagesques en LSF"\n' in out
    assert (
        "    Musée des Augustins, dimanche 21 juin 2026 à 14h30, tarif non précisé\n"
        in out
    )
    # The whole event, its uid with it.
    [prompt] = read
    assert '<event uid="4154446">\nTitre : Visite guidée' in prompt
    assert "lundi 1 juin 2026" in prompt
