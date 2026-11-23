"""Tests of the filters: the start at today unless the question is about the
past, and their description."""

from datetime import date

from cultural_events_rag.retrieval.filters import SearchFilters

TODAY = date(2026, 10, 15)


def test_without_period_the_events_start_from_today() -> None:
    assert SearchFilters().from_today(TODAY).date_from == TODAY


def test_a_period_ending_after_today_starts_from_today() -> None:
    filters = SearchFilters(date_to=date(2026, 12, 24)).from_today(TODAY)

    assert (filters.date_from, filters.date_to) == (TODAY, date(2026, 12, 24))


def test_a_period_in_the_past_is_kept() -> None:
    september = SearchFilters(date_from=date(2026, 9, 1), date_to=date(2026, 9, 30))

    assert september.from_today(TODAY) == september


def test_the_description_lists_each_constraint() -> None:
    filters = SearchFilters(
        date_from=date(2026, 10, 17),
        venue="Jacobins",
        district="Saint-Cyprien",
        free=True,
    )

    assert filters.describe() == (
        "dates: 2026-10-17 to ..., district: Saint-Cyprien, venue: Jacobins, free"
    )
    assert SearchFilters().describe() == "none"
