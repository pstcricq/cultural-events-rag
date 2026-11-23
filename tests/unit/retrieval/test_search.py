"""Tests of the search without Elasticsearch: the filter clauses, the grouping
by event, RRF, and the events of each mode."""

from datetime import date
from typing import Any

import pytest

from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import (
    by_event,
    filter_clauses,
    rrf,
    search_events,
)

TODAY = date(2026, 10, 15)


def test_no_constraint_gives_no_clause() -> None:
    assert filter_clauses(SearchFilters()) == []


def test_a_period_intersects_the_slots_in_the_days_of_the_city() -> None:
    filters = SearchFilters(date_from=date(2026, 11, 19), date_to=date(2026, 11, 20))

    assert filter_clauses(filters) == [
        {
            "range": {
                "timings": {
                    "relation": "intersects",
                    "time_zone": "Europe/Paris",
                    "gte": "2026-11-19",
                    "lte": "2026-11-20||/d",
                }
            }
        }
    ]


def test_an_open_period_has_one_bound() -> None:
    [clause] = filter_clauses(SearchFilters(date_from=TODAY))

    assert set(clause["range"]["timings"]) == {"relation", "time_zone", "gte"}


def test_the_place_and_the_price_have_a_clause_each() -> None:
    filters = SearchFilters(district="Saint-Cyprien", venue="Jacobins", free=True)

    assert filter_clauses(filters) == [
        {"term": {"district": "Saint-Cyprien"}},
        {"match_phrase": {"venue.folded": "Jacobins"}},
        # Free or of unknown price: only the paid events are left out.
        {
            "bool": {
                "should": [
                    {"term": {"is_free": True}},
                    {"bool": {"must_not": {"exists": {"field": "is_free"}}}},
                ],
                "minimum_should_match": 1,
            }
        },
    ]


def hit(uid: str, chunk: int, score: float) -> dict[str, Any]:
    return {
        "_id": f"{uid}-{chunk}",
        "_score": score,
        "_source": {"uid": uid, "text": f"chunk {chunk} of {uid}"},
    }


LEXICAL = [hit("a", 0, 9.0), hit("a", 1, 8.0), hit("b", 0, 7.0), hit("c", 0, 6.0)]
VECTOR = [hit("c", 1, 0.9), hit("b", 0, 0.8), hit("d", 0, 0.7)]


class CannedClient:
    """Answers a lexical search with LEXICAL, a kNN search with VECTOR."""

    def __init__(self) -> None:
        self.queries: list[dict[str, Any]] = []

    def search(self, **request: Any) -> dict[str, Any]:
        self.queries.append(request)
        return {"hits": {"hits": VECTOR if "knn" in request else LEXICAL}}


def test_an_event_counts_once_at_the_rank_of_its_best_chunk() -> None:
    events = by_event(LEXICAL)

    assert list(events) == ["a", "b", "c"]
    assert events["a"]["_id"] == "a-0"


def test_rrf_favours_the_items_ranked_well_in_both() -> None:
    scores = rrf([["a", "b", "c"], ["c", "b", "d"]], k=60)

    assert scores["b"] == pytest.approx(2 / 62)
    # Third then first edges out second twice: 1/63 + 1/61 > 2/62.
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert sorted(scores, key=scores.__getitem__, reverse=True) == ["c", "b", "a", "d"]


@pytest.mark.parametrize(
    ("mode", "uids"),
    [
        ("lexical", ["a", "b", "c"]),
        ("vector", ["c", "b", "d"]),
        ("hybrid", ["c", "b", "a"]),
    ],
)
def test_the_events_of_each_mode(mode: str, uids: list[str]) -> None:
    client = CannedClient()

    matches = search_events(
        client,  # type: ignore[arg-type]
        "events",
        "un concert",
        [0.1, 0.2],
        SearchFilters(),
        mode,  # type: ignore[arg-type]
        k=3,
    )

    assert [match.uid for match in matches] == uids


def test_an_event_keeps_its_ranks_and_its_best_chunk() -> None:
    matches = search_events(
        CannedClient(),  # type: ignore[arg-type]
        "events",
        "un concert",
        [0.1, 0.2],
        SearchFilters(),
        "hybrid",
        k=4,
    )
    c = next(match for match in matches if match.uid == "c")

    assert c.ranks == {"lexical": 3, "vector": 1, "hybrid": 1}
    assert c.chunk.id == "c-1"  # its vector chunk, ranked first
    assert c.chunk.page_content == "chunk 1 of c"
    assert c.chunk.metadata == {"uid": "c"}


def test_both_searches_carry_the_same_filters() -> None:
    client = CannedClient()
    filters = SearchFilters(free=True)

    search_events(client, "events", "un concert", [0.1], filters, "hybrid", k=3)  # type: ignore[arg-type]

    lexical, vector = client.queries
    assert lexical["query"]["bool"]["filter"] == filter_clauses(filters)
    assert vector["knn"]["filter"] == filter_clauses(filters)
    assert lexical["source_excludes"] == vector["source_excludes"] == ["vector"]


def test_a_vector_search_without_a_vector_is_refused() -> None:
    with pytest.raises(ValueError, match="needs the vector"):
        search_events(CannedClient(), "events", "q", None, SearchFilters(), "vector", 3)  # type: ignore[arg-type]
