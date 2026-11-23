"""The ``process`` command: the raw events turned into events of the common format."""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from cultural_events_rag.cli.output import shown
from cultural_events_rag.collection.fetch import LOOKBACK_DAYS, source_name
from cultural_events_rag.collection.files import load_raw, save_events
from cultural_events_rag.collection.process import process_events
from cultural_events_rag.constants import CITY, CULTURAL_AGENDAS
from cultural_events_rag.paths import EVENTS_FILE, RAW_DIR
from cultural_events_rag.settings import get_settings


def _process(args: argparse.Namespace) -> int:
    settings = get_settings()
    source = source_name(settings)
    raw_path = RAW_DIR / f"{source}.json"
    if not raw_path.is_file():
        print(
            f"FAIL no raw events in {shown(raw_path)}: run make fetch", file=sys.stderr
        )
        return 1

    now = datetime.now(UTC)
    since = now - timedelta(days=LOOKBACK_DAYS)
    raw = load_raw(raw_path)
    total = sum(len(events) for events in raw.values())
    print(f"Raw: {total} events <- {shown(raw_path)}")

    report = process_events(raw, source, CULTURAL_AGENDAS, CITY, since, now)
    save_events(report.events, EVENTS_FILE)

    dropped = ", ".join(f"{reason}: {n}" for reason, n in report.dropped.items())
    print(f"Dropped: {dropped or 'none'}")
    print(f"Sessions merged into their activity: {report.merged}")
    print(f"Kept: {len(report.events)} events -> {shown(EVENTS_FILE)}")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the ``process`` command to the parser of ``cultural-events-rag``."""
    process = commands.add_parser(
        "process", help="turn the raw events into the events of the common format"
    )
    process.set_defaults(run=_process)
