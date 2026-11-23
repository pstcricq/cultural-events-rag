"""The French texts of the web interface: errors, the badges of an event
(price, delay, audience), its dates beside the tile of its day, waiting time
and the filters read in a question."""

from datetime import UTC, date, datetime

import pytest

from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.ui.client import ApiError
from cultural_events_rag.ui.text import (
    audience,
    day_tile,
    delay,
    describe_filters,
    error_message,
    price_badge,
    waiting_message,
    when,
)

TODAY = date(2026, 11, 19)


@pytest.mark.parametrize(
    ("error", "start"),
    [
        (ApiError(None, "down", timed_out=True), "L'assistant met trop de temps"),
        (ApiError(None, "down"), "L'assistant est injoignable"),
        (ApiError(422, "too long"), "Cette question n'est pas valide : de 1 à 500"),
        (ApiError(502, "Mistral"), "Le service de génération ne répond pas"),
        (ApiError(503, "no index"), "L'assistant n'est pas prêt"),
        (ApiError(500, "boom"), "Une erreur inattendue s'est produite (code 500)"),
    ],
)
def test_each_error_has_its_message(error: ApiError, start: str) -> None:
    assert error_message(error).startswith(start)


def test_each_price_has_its_badge() -> None:
    assert price_badge(True) == ("Gratuit", "green")
    assert price_badge(False) == ("Payant", "gray")
    assert price_badge(None) == ("Tarif non précisé", "gray")


SATURDAY_EVENING = datetime(2026, 11, 21, 19, 30, tzinfo=TIMEZONE)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 11, 21), "Ce soir"),
        (date(2026, 11, 20), "Demain"),
        (date(2026, 11, 19), "Ce week-end"),  # Thursday of the same week
        (date(2026, 11, 16), "Ce week-end"),  # Monday of the same week
        (date(2026, 11, 15), "Dans 6 jours"),  # the Sunday before
        (date(2026, 11, 14), None),  # a week ahead
        (date(2026, 11, 22), None),  # the day after
    ],
)
def test_the_delay_says_how_soon_within_a_week(
    today: date, expected: str | None
) -> None:
    assert delay(SATURDAY_EVENING, today) == expected


def test_a_slot_today_before_the_evening_is_today() -> None:
    morning = datetime(2026, 11, 21, 10, 0, tzinfo=TIMEZONE)

    assert delay(morning, date(2026, 11, 21)) == "Aujourd'hui"


@pytest.mark.parametrize(
    ("ages", "expected"),
    [
        ((6, 10), "6-10 ans"),
        ((6, None), "Dès 6 ans"),
        ((6, 99), "Dès 6 ans"),
        ((None, 12), "Jusqu'à 12 ans"),
        ((0, 99), None),
        ((None, None), None),
    ],
)
def test_the_audience_is_given_when_the_agenda_says_it(
    ages: tuple[int | None, int | None], expected: str | None
) -> None:
    assert audience(*ages) == expected


def test_one_day_gives_its_slots_alone_beside_its_tile() -> None:
    dates = "samedi 21 novembre 2026, 19h30-22h00, 22h30-23h30"

    assert when(SATURDAY_EVENING, dates) == (True, "19h30-22h00, 22h30-23h30")


def test_several_days_keep_their_dates() -> None:
    dates = "samedi 21 novembre 2026, 19h30-22h00; dimanche 22 novembre 2026, 16h00"

    assert when(SATURDAY_EVENING, dates) == (False, dates)


def test_a_series_keeps_its_range() -> None:
    series = "du jeudi 1 octobre 2026 au jeudi 31 décembre 2026 (40 créneaux)"

    assert when(SATURDAY_EVENING, series) == (False, series)


def test_the_tile_gives_the_day_and_time_of_the_first_slot_in_toulouse() -> None:
    late = datetime(2026, 11, 21, 23, 30, tzinfo=UTC)  # Sunday 00:30 in Toulouse

    assert day_tile(datetime(2026, 11, 21, 19, 30, tzinfo=TIMEZONE)) == (
        "sam.",
        "21",
        "novembre",
        "19h30",
    )
    assert day_tile(late) == ("dim.", "22", "novembre", "0h30")


def test_the_waiting_message_gives_the_quota_when_known() -> None:
    assert "jusqu'à 30 s" in waiting_message(2)
    assert "Comptez" not in waiting_message(None)


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (SearchFilters(), []),
        (SearchFilters(date_from=TODAY), ["Événements à venir"]),
        (
            SearchFilters(date_from=date(2026, 12, 1)),
            ["À partir du mardi 1 décembre 2026"],
        ),
        (
            SearchFilters(date_to=date(2026, 9, 20)),
            ["Jusqu'au dimanche 20 septembre 2026"],
        ),
        (
            SearchFilters(date_from=date(2026, 11, 21), date_to=date(2026, 11, 21)),
            ["Le samedi 21 novembre 2026"],
        ),
        (
            SearchFilters(
                date_from=date(2026, 11, 21),
                date_to=date(2026, 11, 22),
                district="Saint-Cyprien",
                venue="Bikini",
                free=True,
            ),
            [
                "Du samedi 21 novembre 2026 au dimanche 22 novembre 2026",
                "Quartier : Saint-Cyprien",
                "Lieu : Bikini",
                "Gratuit ou tarif non précisé",
            ],
        ),
    ],
)
def test_the_filters_are_described(filters: SearchFilters, expected: list[str]) -> None:
    assert describe_filters(filters, TODAY) == expected
