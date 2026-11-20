"""The download of the raw events: the source, the events of each agenda."""

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

import httpx

from cultural_events_rag.collection.sources import (
    EventSource,
    OpenAgendaSource,
    OpenDataSoftSource,
)
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.models import Agenda, RawEvents
from cultural_events_rag.settings import Settings

# The past days collected besides the upcoming events: a year, for the
# questions about the past.
LOOKBACK_DAYS = 365

logger = logging.getLogger(__name__)


def event_cap(max_events: int | Literal["all"] | None) -> int | None:
    """The most events to collect, None for all of them, from MAX_EVENTS: a
    number, or all. Unset, refused."""
    if max_events is None:
        raise MissingSettingError(
            "MAX_EVENTS is not set: add it to .env, a number or all"
        )
    return None if max_events == "all" else max_events


def select_source(settings: Settings, client: httpx.Client) -> EventSource:
    """The official API with a key, the OpenDataSoft dataset without."""
    if settings.openagenda_api_key:
        key = settings.openagenda_api_key.get_secret_value()
        return OpenAgendaSource(client, key)
    logger.warning("OPENAGENDA_API_KEY not set: falling back to OpenDataSoft")
    return OpenDataSoftSource(client)


def fetch_new(
    source: EventSource,
    agenda: Agenda,
    city: str,
    since: datetime,
    limit: int | None,
    upcoming: bool,
    seen: set[str],
) -> list[dict[str, Any]]:
    """Up to ``limit`` events of ``agenda`` not in ``seen``, then added to it.
    An event already seen is skipped, and one more is fetched to replace it
    while the agenda has some."""
    skipped = 0
    while True:
        size = None if limit is None else limit + skipped
        fetched = source.fetch(agenda, city, since, size, upcoming)
        new = [data for data in fetched if str(data["uid"]) not in seen]
        if size is None or len(fetched) < size or len(new) >= size - skipped:
            break
        skipped = len(fetched) - len(new)  # grows at each round: the loop ends
    new = new if limit is None else new[:limit]
    seen.update(str(data["uid"]) for data in new)
    return new


def fetch_agendas(
    source: EventSource,
    agendas: Sequence[Agenda],
    city: str,
    since: datetime,
    max_events: int | None,
) -> RawEvents:
    """The raw events of each agenda, the upcoming ones first.

    With a cap, the quota is split evenly between the agendas, so that a large
    one (the libraries) does not fill the whole sample. Each quota goes to the
    upcoming events first, then to the most recently finished ones: the
    assistant recommends outings, past events only answer questions about the
    past. An event shared by several agendas is kept by the first one only and
    does not count in the quota of the others.
    """
    quota = max(1, max_events // len(agendas)) if max_events else None
    raw: RawEvents = {}
    seen: set[str] = set()  # the uids already fetched, from any agenda
    for agenda in agendas:
        upcoming = fetch_new(source, agenda, city, since, quota, True, seen)
        rest = None if quota is None else quota - len(upcoming)
        past = []
        if rest != 0:
            past = fetch_new(source, agenda, city, since, rest, False, seen)
        raw[agenda.uid] = upcoming + past
        logger.info(
            "%-62s %5d events (%d upcoming)",
            agenda.title,
            len(raw[agenda.uid]),
            len(upcoming),
        )
    return raw
