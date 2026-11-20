"""The events cleaned whatever their source: outside the city, finished before
the period or seen twice, dropped and counted; the sessions of one activity
merged into one event."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cultural_events_rag.collection.cleaning import clean_events, merge_sessions
from cultural_events_rag.models import Event, Location, Timing

SINCE = datetime(2026, 6, 1, tzinfo=UTC)


def test_an_event_outside_the_city_is_dropped(event: Event) -> None:
    elsewhere = event.model_copy(update={"location": Location(city="Blagnac")})

    kept, dropped = clean_events([elsewhere], "Toulouse", SINCE)

    assert kept == []
    assert dropped == {"out_of_area": 1}


def test_an_event_finished_before_the_period_is_dropped(event: Event) -> None:
    kept, dropped = clean_events(
        [event], "Toulouse", event.last_end + timedelta(days=1)
    )

    assert kept == []
    assert dropped == {"out_of_period": 1}


def test_an_event_is_kept_once_and_the_city_matched_whatever_the_case(
    event: Event,
) -> None:
    upper = event.model_copy(update={"location": Location(city="TOULOUSE")})

    kept, dropped = clean_events([event, upper], "toulouse", SINCE)

    assert kept == [event]
    assert dropped == {"duplicate": 1}


# --- Sessions published as separate events -----------------------------------

NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)


def session(event: Event, uid: str, day: int, **changes: Any) -> Event:
    """`event` (an activity) published for one session, on `day` October 2026 at 10h UTC."""
    begin = datetime(2026, 10, day, 10, tzinfo=UTC)
    return event.model_copy(
        update={
            "uid": uid,
            "url": f"https://openagenda.com/events/{uid}",
            "timings": [Timing(begin=begin, end=begin + timedelta(hours=1))],
        }
        | changes
    )


def test_sessions_of_an_activity_become_one_event(event: Event) -> None:
    sessions = [
        session(event, "1", 25),
        session(event, "2", 10),
        session(event, "3", 18),
    ]

    merged = merge_sessions(sessions, NOW)

    assert len(merged) == 1
    assert [t.begin.day for t in merged[0].timings] == [10, 18, 25]  # sorted


def test_merged_event_is_its_next_session(event: Event) -> None:
    # Its uid and link: the card points to the session the user can still book
    sessions = [
        session(event, "1", 25),
        session(event, "2", 10),
        session(event, "3", 21),
    ]

    merged = merge_sessions(sessions, NOW)[0]

    assert (merged.uid, merged.url) == ("3", "https://openagenda.com/events/3")


def test_finished_activity_is_its_last_session(event: Event) -> None:
    sessions = [session(event, "1", 5), session(event, "2", 12)]

    assert merge_sessions(sessions, NOW)[0].uid == "2"


def test_title_matched_whatever_the_case_and_spaces(event: Event) -> None:
    sessions = [
        session(event, "1", 20),
        session(event, "2", 21, title=f" {event.title.upper()}"),
    ]

    assert len(merge_sessions(sessions, NOW)) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Autre visite"},
        {"description": "Une autre visite."},
        {"long_description": "Un autre parcours."},
        {"location": Location(name="Couvent des Jacobins")},
        {"conditions": "Tarif : 5 €"},
        {"status": "Annulé"},  # a cancelled session stays visible as such
        {"age_min": 6},
    ],
)
def test_different_activities_stay_apart(event: Event, change: dict[str, Any]) -> None:
    sessions = [session(event, "1", 20), session(event, "2", 21, **change)]

    assert [e.uid for e in merge_sessions(sessions, NOW)] == ["1", "2"]


def test_merged_event_gathers_keywords_and_latest_update(event: Event) -> None:
    sessions = [
        session(
            event,
            "1",
            20,
            keywords=["visite"],
            updated_at=datetime(2026, 9, 1, tzinfo=UTC),
        ),
        session(event, "2", 21, keywords=["visite", "musée"], updated_at=None),
        session(
            event,
            "3",
            22,
            keywords=["famille"],
            updated_at=datetime(2026, 9, 5, tzinfo=UTC),
        ),
    ]

    merged = merge_sessions(sessions, NOW)[0]

    assert merged.keywords == ["visite", "musée", "famille"]
    assert merged.updated_at == datetime(2026, 9, 5, tzinfo=UTC)


def test_same_session_twice_counts_once(event: Event) -> None:
    sessions = [session(event, "1", 20), session(event, "2", 20)]

    assert len(merge_sessions(sessions, NOW)[0].timings) == 1


def test_lone_events_are_kept_in_order(event: Event) -> None:
    events = [session(event, "1", 20, title="B"), session(event, "2", 21, title="A")]

    assert merge_sessions(events, NOW) == events
