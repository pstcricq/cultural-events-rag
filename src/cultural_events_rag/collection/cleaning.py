"""The cleaning of the events of the common format: events outside the city or
finished before the period dropped, duplicates dropped, and the sessions of one
activity merged into one event."""

from collections import Counter
from collections.abc import Hashable, Iterable
from datetime import datetime

from cultural_events_rag.models import Event


def clean_events(
    events: Iterable[Event], city: str, since: datetime
) -> tuple[list[Event], Counter[str]]:
    """Return the events in ``city`` not finished before ``since``, each once,
    and the number of events dropped for each reason."""
    kept: list[Event] = []
    dropped: Counter[str] = Counter()
    seen: set[str] = set()
    for event in events:
        if (event.location.city or "").casefold() != city.casefold():
            dropped["out_of_area"] += 1
        elif event.last_end < since:
            dropped["out_of_period"] += 1
        elif event.uid in seen:
            dropped["duplicate"] += 1
        else:
            seen.add(event.uid)
            kept.append(event)
    return kept, dropped


def _activity(event: Event) -> Hashable:
    """Return what the sessions of one activity share: every field but their
    dates and links."""
    return (
        " ".join(event.title.casefold().split()),
        event.location.name,
        event.description,
        event.long_description,
        event.conditions,
        event.status,
        event.age_min,
        event.age_max,
    )


def _merge(sessions: list[Event], now: datetime) -> Event:
    """Merge the sessions of one activity into one event: the next session,
    else the last one, gives its uid and link, all of them their dates."""
    upcoming = [s for s in sessions if s.last_end >= now]
    if upcoming:
        main = min(upcoming, key=lambda s: s.first_begin)
    else:
        main = max(sessions, key=lambda s: s.last_end)
    timings = {(t.begin, t.end): t for s in sessions for t in s.timings}
    updates = [s.updated_at for s in sessions if s.updated_at]
    return main.model_copy(
        update={
            "timings": [timings[key] for key in sorted(timings)],
            "keywords": list(dict.fromkeys(k for s in sessions for k in s.keywords)),
            "updated_at": max(updates, default=None),
        }
    )


def merge_sessions(events: Iterable[Event], now: datetime) -> list[Event]:
    """Merge the events that are sessions of the same activity, such as a
    guided tour published once per date. The order of first appearance is kept."""
    activities: dict[Hashable, list[Event]] = {}
    for event in events:
        activities.setdefault(_activity(event), []).append(event)
    return [
        sessions[0] if len(sessions) == 1 else _merge(sessions, now)
        for sessions in activities.values()
    ]
