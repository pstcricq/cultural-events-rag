"""The places of the index, and cultural-events-rag analyze against a real
Elasticsearch: the districts and venues of the index served found in the
question."""

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.cli import main
from cultural_events_rag.elastic import index_alias
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.models import Event
from cultural_events_rag.retrieval.query_analysis import Place, PlaceMatcher
from cultural_events_rag.settings import Settings


@pytest.fixture
def indexed(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_index(client, [event], DeterministicFakeEmbedding(size=16), settings)
    monkeypatch.setattr(
        "cultural_events_rag.cli.analyze.get_settings", lambda: settings
    )


def test_the_places_are_those_of_the_index(
    indexed: None, client: Elasticsearch, settings: Settings
) -> None:
    places = PlaceMatcher.from_index(client, index_alias(settings))

    assert places.match("Que voir au musée des Augustins ?") == Place(venue="Augustins")
    assert places.match("Que faire aux Carmes ?") == Place(
        district="Capitole / Arnaud Bernard / Carmes"
    )


def test_analyze_finds_the_venue_of_the_index(
    indexed: None, capsys: pytest.CaptureFixture[str]
) -> None:
    question = "Que voir au musée des Augustins ce week-end ?"

    assert main(["analyze", question, "--today", "2026-10-15"]) == 0

    out = capsys.readouterr().out
    assert "places: 1 districts, 1 venues" in out
    assert "Filters: dates: 2026-10-17 to 2026-10-18, venue: Augustins" in out


def test_analyze_before_any_index(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "cultural_events_rag.cli.analyze.get_settings", lambda: settings
    )

    assert main(["analyze", "Un concert ce soir ?"]) == 1

    assert "run make index" in capsys.readouterr().err
