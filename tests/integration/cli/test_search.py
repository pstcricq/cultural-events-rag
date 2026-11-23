"""cultural-events-rag search end to end against a real Elasticsearch, with a
fake embedding model and a fake reranker: the events found, reranked, and an
index built otherwise or a missing rerank extra refused."""

import sys
from collections.abc import Sequence

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


class Constant:
    """Scores every candidate alike."""

    def __init__(self, model: str) -> None:
        self.model = model

    def scores(self, question: str, texts: Sequence[str]) -> list[float]:
        return [0.5] * len(texts)


def test_search_reranks_with_the_model_of_the_code(
    indexed: None,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "cultural_events_rag.cli.search.RERANK_MODEL", "a/cross-encoder"
    )
    monkeypatch.setattr("cultural_events_rag.cli.search.CrossEncoderReranker", Constant)

    assert (
        main(
            [
                "search",
                "Une visite guidée",
                "--mode",
                "hybrid",
                "--rerank",
                "--today",
                "2026-06-01",
            ]
        )
        == 0
    )

    out = capsys.readouterr().out
    assert "Reranker: a/cross-encoder, loaded in " in out
    assert "hybrid search reranked by a/cross-encoder (20 candidates)" in out
    assert "score 0.5, before reranking: hybrid 1 (lexical 1, vector 1), event" in out


def test_search_names_the_missing_extra(
    indexed: None,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "cultural_events_rag.cli.search.RERANK_MODEL", "a/cross-encoder"
    )

    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # not installed

    assert main(["search", "Une visite guidée", "--mode", "hybrid", "--rerank"]) == 1

    assert (
        "the reranking needs the rerank extra: run make install"
        in capsys.readouterr().err
    )
