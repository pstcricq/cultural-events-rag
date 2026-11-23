"""Tests of the download: the source chosen by the key, the quota of each
agenda, the upcoming events first, a shared event kept once."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from cultural_events_rag.collection.fetch import (
    fetch_agendas,
    select_source,
    source_name,
)
from cultural_events_rag.collection.sources import OpenAgendaSource, OpenDataSoftSource
from cultural_events_rag.models import Agenda, RawEvents
from cultural_events_rag.settings import Settings

SINCE = datetime(2025, 10, 15, tzinfo=UTC)
AGENDAS = [Agenda(1, "A"), Agenda(2, "B"), Agenda(3, "C")]


class FakeSource:
    """Per agenda, ``upcoming`` upcoming events (uids agenda * 1000 + i) and
    ``past`` past ones (uids agenda * 1000 + 500 + i). ``shared`` upcoming
    events come first in every agenda, as an event published by several."""

    name = "fake"

    def __init__(self, upcoming: int, past: int = 50, shared: int = 0) -> None:
        self.available = {True: upcoming, False: past}
        self.shared = [str(9000 + i) for i in range(shared)]
        self.calls: list[tuple[str, bool, int | None]] = []

    def fetch(
        self,
        agenda: Agenda,
        city: str,
        since: datetime,
        limit: int | None,
        upcoming: bool,
    ) -> list[dict[str, Any]]:
        self.calls.append((agenda.title, upcoming, limit))
        first = agenda.uid * 1000 + (0 if upcoming else 500)
        own = [str(first + i) for i in range(self.available[upcoming])]
        uids = (self.shared if upcoming else []) + own
        return [{"uid": uid} for uid in uids[:limit]]


def uids(raw: RawEvents) -> list[str]:
    return [data["uid"] for events in raw.values() for data in events]


@pytest.mark.parametrize(
    ("api_key", "expected"),
    [("secret", OpenAgendaSource), (None, OpenDataSoftSource)],
)
def test_without_key_the_source_falls_back_to_opendatasoft(
    api_key: str | None, expected: type
) -> None:
    key = SecretStr(api_key) if api_key else None
    settings = Settings(_env_file=None, openagenda_api_key=key)

    with httpx.Client() as client:
        source = select_source(settings, client)
    assert isinstance(source, expected)
    assert source_name(settings) == source.name


def test_the_cap_is_split_between_the_agendas() -> None:
    source = FakeSource(upcoming=50)

    raw = fetch_agendas(source, AGENDAS, "Toulouse", SINCE, max_events=10)

    assert source.calls == [("A", True, 3), ("B", True, 3), ("C", True, 3)]
    assert {uid: len(events) for uid, events in raw.items()} == {1: 3, 2: 3, 3: 3}


def test_past_events_complete_the_quota() -> None:
    source = FakeSource(upcoming=1)

    raw = fetch_agendas(source, AGENDAS[:1], "Toulouse", SINCE, max_events=4)

    assert source.calls == [("A", True, 4), ("A", False, 3)]
    assert uids(raw) == ["1000", "1500", "1501", "1502"]


def test_a_shared_event_is_kept_once_and_counted_once() -> None:
    source = FakeSource(upcoming=50, shared=1)

    raw = fetch_agendas(source, AGENDAS[:2], "Toulouse", SINCE, max_events=6)

    assert uids(raw) == ["9000", "1000", "1001", "2000", "2001", "2002"]
    assert source.calls[1:] == [("B", True, 3), ("B", True, 4)]  # one more for B


def test_an_agenda_with_only_shared_events_ends() -> None:
    source = FakeSource(upcoming=0, past=0, shared=2)

    raw = fetch_agendas(source, AGENDAS[:2], "Toulouse", SINCE, max_events=4)

    assert uids(raw) == ["9000", "9001"]


def test_without_cap_every_event_is_fetched() -> None:
    source = FakeSource(upcoming=20, past=30)

    raw = fetch_agendas(source, AGENDAS, "Toulouse", SINCE, max_events=None)

    assert [call[1:] for call in source.calls] == [(True, None), (False, None)] * 3
    assert len(uids(raw)) == 150
