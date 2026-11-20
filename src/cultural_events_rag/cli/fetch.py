"""The ``cultural-events-rag fetch`` command: the raw events of the agendas."""

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx

from cultural_events_rag.cli.output import shown
from cultural_events_rag.collection.fetch import (
    LOOKBACK_DAYS,
    event_cap,
    fetch_agendas,
    select_source,
)
from cultural_events_rag.collection.files import save_raw
from cultural_events_rag.constants import CITY, CULTURAL_AGENDAS
from cultural_events_rag.errors import MissingSettingError, SourceError
from cultural_events_rag.paths import RAW_DIR
from cultural_events_rag.settings import get_settings


def _client() -> httpx.Client:
    """The HTTP client of the sources, replaced by the tests."""
    return httpx.Client(timeout=30)


def _max_events(text: str) -> int | Literal["all"]:
    """A number of events above 0, or all."""
    if text == "all":
        return "all"
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError("a number above 0, or all")
    return int(text)


def _fetch(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        cap = event_cap(args.max_events or settings.max_events)
    except MissingSettingError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    since = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        with _client() as client:
            source = select_source(settings, client)
            print(
                f"Source: {source.name}, city: {CITY}, "
                f"since: {since.date()}, cap: {cap or 'all'}\n"
            )
            raw = fetch_agendas(source, CULTURAL_AGENDAS, CITY, since, cap)
    except SourceError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    path = RAW_DIR / f"{source.name}.json"
    save_raw(raw, path)
    total = sum(len(events) for events in raw.values())
    print(f"\n{total} raw events -> {shown(path)}")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag fetch`` to the cultural-events-rag command."""
    fetch = commands.add_parser(
        "fetch", help="download the raw events of the cultural agendas"
    )
    fetch.add_argument(
        "--max-events",
        type=_max_events,
        help="at most this many events, or all (default: MAX_EVENTS)",
    )
    fetch.set_defaults(run=_fetch)
