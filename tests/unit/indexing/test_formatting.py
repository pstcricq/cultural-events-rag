"""Tests of the French formatting: days, slots grouped by day in Paris time,
long series as a range, the place, the audience."""

from datetime import UTC, date, datetime, timedelta

import pytest

from cultural_events_rag.indexing.formatting import (
    format_age,
    format_dates,
    format_day,
    format_location,
    format_timings,
)
from cultural_events_rag.models import Location, Timing


def slot(year: int, month: int, day: int, hour: int, minutes: int = 60) -> Timing:
    """A timing starting at the given UTC hour."""
    begin = datetime(year, month, day, hour, tzinfo=UTC)
    return Timing(begin=begin, end=begin + timedelta(minutes=minutes))


# --- Dates -------------------------------------------------------------------


def test_format_day_in_french() -> None:
    assert format_day(date(2026, 6, 21)) == "dimanche 21 juin 2026"
    assert format_day(date(2026, 8, 3)) == "lundi 3 août 2026"


def test_single_day_converted_to_paris_time() -> None:
    # 12:30 UTC is 14:30 in Paris in summer (UTC+2)
    timing = Timing(
        begin=datetime(2026, 6, 21, 12, 30, tzinfo=UTC),
        end=datetime(2026, 6, 21, 13, 30, tzinfo=UTC),
    )

    assert format_timings([timing]) == "Date : dimanche 21 juin 2026, 14h30-15h30"


def test_slots_grouped_by_day_and_sorted() -> None:
    timings = [slot(2026, 9, 20, 8), slot(2026, 9, 19, 12), slot(2026, 9, 19, 8)]

    assert format_timings(timings) == (
        "Dates :\n"
        "- samedi 19 septembre 2026, 10h00-11h00, 14h00-15h00\n"
        "- dimanche 20 septembre 2026, 10h00-11h00"
    )


def test_long_series_summarized_as_range() -> None:
    timings = [slot(2026, 1, 3 + i, 18) for i in range(10)]

    assert format_timings(timings) == (
        "Dates : du samedi 3 janvier 2026 au lundi 12 janvier 2026 (10 créneaux)"
    )


def test_the_dates_alone_on_one_line() -> None:
    days = [slot(2026, 9, 20, 8), slot(2026, 9, 19, 8)]
    series = [slot(2026, 1, 3 + i, 18) for i in range(10)]

    assert format_dates(days) == (
        "samedi 19 septembre 2026, 10h00-11h00; dimanche 20 septembre 2026, 10h00-11h00"
    )
    assert format_dates(series) == (
        "du samedi 3 janvier 2026 au lundi 12 janvier 2026 (10 créneaux)"
    )


# --- Location and audience ---------------------------------------------------


def test_format_location() -> None:
    location = Location(
        name="Le Cratère", address="95 Grande-Rue Saint-Michel", district="Busca"
    )

    assert (
        format_location(location)
        == "Le Cratère, 95 Grande-Rue Saint-Michel (quartier Busca)"
    )
    assert format_location(Location(name="ABC", city="Toulouse")) == "ABC, Toulouse"
    assert format_location(Location()) is None


@pytest.mark.parametrize(
    ("age_min", "age_max", "expected"),
    [
        (None, None, None),
        (0, 99, None),
        (0, 120, None),
        (7, None, "à partir de 7 ans"),
        (12, 99, "à partir de 12 ans"),
        (3, 6, "de 3 à 6 ans"),
        (0, 6, "jusqu'à 6 ans"),
    ],
)
def test_format_age(
    age_min: int | None, age_max: int | None, expected: str | None
) -> None:
    assert format_age(age_min, age_max) == expected
