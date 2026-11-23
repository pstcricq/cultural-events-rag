"""The search against a real Elasticsearch, with a fake embedding model: each
filter kept by the index (the days of the city, part of a venue name in any
spelling, the price, the district), each mode, and an event split into chunks
found once."""

from datetime import date, datetime

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.elastic import index_alias
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.indexing.chunking import make_splitter
from cultural_events_rag.indexing.documents import events_to_documents
from cultural_events_rag.models import Event, Timing
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import retrieve, search_events
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)


def _event(
    event: Event,
    uid: str,
    title: str,
    venue: str,
    begin: str,
    end: str,
    **update: object,
) -> Event:
    return event.model_copy(
        update={
            "uid": uid,
            "title": title,
            "location": event.location.model_copy(update={"name": venue}),
            "timings": [
                Timing(
                    begin=datetime.fromisoformat(begin), end=datetime.fromisoformat(end)
                )
            ],
            **update,
        }
    )


@pytest.fixture
def events(event: Event) -> list[Event]:
    return [
        # 23:30 to 00:30 in Paris: on the 19th and the 20th.
        _event(
            event,
            "jazz",
            "Concert de jazz",
            "Chapelle des Carmélites",
            "2026-11-19T23:30:00+01:00",
            "2026-11-20T00:30:00+01:00",
            is_free=True,
            long_description="Un trio de jazz joue toute la nuit.",
        ),
        _event(
            event,
            "expo",
            "Exposition de peinture",
            "Couvent des Jacobins",
            "2026-11-21T10:00:00+01:00",
            "2026-11-21T18:00:00+01:00",
            is_free=False,
            location=event.location.model_copy(
                update={"name": "Couvent des Jacobins", "district": "Saint-Cyprien"}
            ),
        ),
        _event(
            event,
            "dessin",
            "Atelier de dessin",
            "chapelle des carmélites",
            "2026-12-05T14:00:00+01:00",
            "2026-12-05T16:00:00+01:00",
            long_description=" ".join(["Un atelier de dessin au fusain."] * 60),
        ),
    ]


@pytest.fixture
def index(client: Elasticsearch, settings: Settings, events: list[Event]) -> str:
    build_index(client, events, FAKE, settings)
    return index_alias(settings)


@pytest.mark.parametrize(
    ("filters", "uids"),
    [
        # The days of the city: the slot of the night counts on both.
        (
            SearchFilters(date_from=date(2026, 11, 19), date_to=date(2026, 11, 19)),
            ["jazz"],
        ),
        (
            SearchFilters(date_from=date(2026, 11, 20), date_to=date(2026, 11, 20)),
            ["jazz"],
        ),
        (SearchFilters(date_from=date(2026, 11, 18), date_to=date(2026, 11, 18)), []),
        (SearchFilters(date_from=date(2026, 11, 21)), ["dessin", "expo"]),
        # Part of a venue name, in any case, with or without its accents.
        (SearchFilters(venue="Carmélites"), ["dessin", "jazz"]),
        (SearchFilters(venue="carmelites"), ["dessin", "jazz"]),
        (SearchFilters(venue="Jacobins"), ["expo"]),
        # Free, or of unknown price: the drawing workshop gives none.
        (SearchFilters(free=True), ["dessin", "jazz"]),
        (SearchFilters(district="Saint-Cyprien"), ["expo"]),
    ],
    ids=lambda value: value.describe() if isinstance(value, SearchFilters) else None,
)
def test_the_filters_keep_the_right_events(
    client: Elasticsearch, index: str, filters: SearchFilters, uids: list[str]
) -> None:
    # Any vector: the vector search ranks every entry the filters keep.
    vector = FAKE.embed_query("une sortie")
    every = search_events(client, index, "", vector, filters, "vector", k=10)

    assert sorted(match.uid for match in every) == uids


def test_the_lexical_search_ranks_by_the_words(
    client: Elasticsearch, index: str
) -> None:
    [first, *_] = search_events(
        client, index, "un concert de jazz", None, SearchFilters(), "lexical", k=3
    )

    assert first.uid == "jazz"
    assert set(first.ranks) == {"lexical"}


def test_the_vector_search_ranks_by_the_vector(
    client: Elasticsearch, index: str, events: list[Event]
) -> None:
    [document, *_] = events_to_documents([events[1]], make_splitter(1000, 150))
    vector = FAKE.embed_query(document.page_content)

    [first, *_] = search_events(
        client, index, "", vector, SearchFilters(), "vector", k=3
    )

    assert first.uid == "expo"
    assert first.score == pytest.approx(
        1.0
    )  # its own vector: cosine 1, scored (1 + 1) / 2


def test_an_event_in_several_chunks_is_found_once(
    client: Elasticsearch,
    settings: Settings,
    events: list[Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cultural_events_rag.indexing.build.CHUNK_SIZE", 300)
    monkeypatch.setattr("cultural_events_rag.indexing.build.CHUNK_OVERLAP", 30)
    report = build_index(client, events, FAKE, settings)
    assert report.documents > len(events)

    matches = search_events(
        client,
        index_alias(settings),
        "atelier dessin fusain",
        None,
        SearchFilters(),
        "lexical",
        k=10,
    )

    assert sorted(match.uid for match in matches) == ["dessin"]


def test_retrieve_analyzes_then_searches_in_both(
    client: Elasticsearch, index: str
) -> None:
    retrieval = retrieve(
        client,
        index,
        "Un concert gratuit aux Carmélites ?",
        date(2026, 11, 18),
        "hybrid",
        5,
        FAKE,
    )

    assert retrieval.filters == SearchFilters(
        date_from=date(2026, 11, 18), venue="Carmélites", free=True
    )
    assert {match.uid for match in retrieval.matches} == {"jazz", "dessin"}
    assert set(retrieval.matches[0].ranks) == {"lexical", "vector", "hybrid"}
