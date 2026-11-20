"""The raw events turned into the events of the common format: parsed by the
parser of their source, cleaned, the sessions of one activity merged."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from cultural_events_rag.collection.cleaning import clean_events, merge_sessions
from cultural_events_rag.collection.parsing import PARSERS, parse_events
from cultural_events_rag.models import Agenda, Event, RawEvents


@dataclass
class ProcessReport:
    """The events kept, the raw events dropped for each reason, and the sessions
    merged into the event of their activity."""

    events: list[Event] = field(default_factory=list)
    dropped: Counter[str] = field(default_factory=Counter)
    merged: int = 0


def process_events(
    raw: RawEvents,
    source: str,
    agendas: Sequence[Agenda],
    city: str,
    since: datetime,
    now: datetime,
) -> ProcessReport:
    """The events of ``raw``, fetched from ``source``: those in ``city`` and
    not finished before ``since``, each activity once (``now`` tells which of
    its sessions is the next one). An agenda left out of ``agendas`` since the
    download is left out too."""
    by_uid = {agenda.uid: agenda for agenda in agendas}
    items = (
        (by_uid[uid], data)
        for uid, events in raw.items()
        if uid in by_uid
        for data in events
    )
    parsed, invalid = parse_events(items, PARSERS[source])
    cleaned, dropped = clean_events(parsed, city, since)
    if invalid:
        dropped["invalid"] = invalid
    merged = merge_sessions(cleaned, now)
    return ProcessReport(merged, dropped, len(cleaned) - len(merged))
