"""cultural-events-rag search end to end against a real Elasticsearch, with a
fake embedding model: the events found, and an index built otherwise
refused."""

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.cli import main
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)


@pytest.fixture
def indexed(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_index(client, [event], FAKE, settings)
    monkeypatch.setattr("cultural_events_rag.cli.search.get_settings", lambda: settings)
    monkeypatch.setattr(
        "cultural_events_rag.cli.search.make_embeddings", lambda _: FAKE
    )


def test_search_prints_the_filters_and_the_events(
    indexed: None, capsys: pytest.CaptureFixture[str]
) -> None:
    question = "Une visite guidée au musée des Augustins en juin ?"

    assert main(["search", question, "--mode", "hybrid", "--today", "2026-06-01"]) == 0

    out = capsys.readouterr().out
    assert "Asked on 2026-06-01, hybrid search, 5 events at most, " in out
    assert "Filters: dates: 2026-06-01 to 2026-06-30, venue: Augustins" in out
    assert ' 1. Visite guidée "Les peintres caravagesques en LSF"\n' in out
    assert (
        "    Musée des Augustins, dimanche 21 juin 2026 à 14h30, tarif non précisé\n"
        in out
    )
    assert ", lexical 1, vector 1, event 4154446, chunk 0\n" in out


def test_search_with_no_event_left(
    indexed: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            ["search", "Un concert demain", "--mode", "hybrid", "--today", "2026-06-01"]
        )
        == 0
    )

    assert "No event" in capsys.readouterr().out


def test_search_refuses_an_index_built_otherwise(
    indexed: None,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "cultural_events_rag.indexing.build.EMBEDDING_MODEL", "another-model"
    )

    assert main(["search", "Un concert", "--mode", "lexical"]) == 1

    assert "outdated index: embedding_model" in capsys.readouterr().err
