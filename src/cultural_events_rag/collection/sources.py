"""The two sources of events: the official Open Agenda API (v2), and the
OpenDataSoft dataset of the public agendas, which needs no key."""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

import httpx

from cultural_events_rag.errors import SourceError
from cultural_events_rag.models import Agenda
from cultural_events_rag.retry import make_retrying

Params = list[tuple[str, str | int | float | bool | None]]


class EventSource(Protocol):
    name: str

    def fetch(
        self,
        agenda: Agenda,
        city: str,
        since: datetime,
        limit: int | None,
        upcoming: bool,
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` raw events of ``agenda`` in ``city``.

        With ``upcoming``, the ongoing and upcoming events, the most recently
        updated first. Without, the events finished since ``since``, the most
        recent first."""
        ...


def get_json(
    client: httpx.Client,
    url: str,
    params: Params,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    backoff: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET a JSON document, transient errors retried."""

    def request() -> Any:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    host = httpx.URL(url).host
    retrying = make_retrying(f"Request to {host}", retries, backoff, sleep)
    try:
        return retrying(request)
    except httpx.HTTPStatusError as exc:
        status, text = exc.response.status_code, exc.response.text[:200]
        raise SourceError(f"HTTP {status} on {url}: {text}") from exc
    except httpx.TransportError as exc:
        raise SourceError(f"Network error on {url}: {exc}") from exc


class OpenAgendaSource:
    """The official API: the events of one agenda, paginated with ``after``."""

    name = "openagenda"
    url = "https://api.openagenda.com/v2/agendas/{uid}/events"
    page_size = 300  # API maximum

    def __init__(self, client: httpx.Client, api_key: str) -> None:
        self.client = client
        self.headers = {"key": api_key}

    def fetch(
        self,
        agenda: Agenda,
        city: str,
        since: datetime,
        limit: int | None,
        upcoming: bool,
    ) -> list[dict[str, Any]]:
        if upcoming:
            selection: Params = [
                ("relative[]", "current"),
                ("relative[]", "upcoming"),
                ("sort", "updatedAt.desc"),
            ]
        else:
            selection = [
                ("relative[]", "passed"),
                ("timings[gte]", since.isoformat()),
                ("sort", "lastTiming.desc"),
            ]
        url = self.url.format(uid=agenda.uid)
        events: list[dict[str, Any]] = []
        after: list[str] = []
        while limit is None or len(events) < limit:
            size = self.page_size
            if limit is not None:
                size = min(size, limit - len(events))
            params: Params = [
                ("adminLevel4[]", city),
                *selection,
                ("detailed", "1"),
                ("monolingual", "fr"),
                ("longDescriptionFormat", "HTML"),
                ("size", str(size)),
                *(("after[]", str(value)) for value in after),
            ]
            page = get_json(self.client, url, params, self.headers)
            batch = page.get("events") or []
            events.extend(batch)
            after = page.get("after") or []
            if not batch or not after:
                break
        return events


class OpenDataSoftSource:
    """The OpenDataSoft dataset of the public Open Agenda agendas, paginated
    with ``offset``."""

    name = "opendatasoft"
    url = (
        "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
        "evenements-publics-openagenda/records"
    )
    page_size = 100  # API maximum

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def fetch(
        self,
        agenda: Agenda,
        city: str,
        since: datetime,
        limit: int | None,
        upcoming: bool,
    ) -> list[dict[str, Any]]:
        city_literal = city.replace('"', '\\"')
        if upcoming:
            period = "lastdate_end >= now()"
            order = "updatedat desc"
        else:
            day = since.date().isoformat()
            period = f"lastdate_end < now() and lastdate_end >= date'{day}'"
            order = "lastdate_end desc"
        where = (
            f'location_city="{city_literal}" '
            f'and originagenda_uid="{agenda.uid}" and {period}'
        )
        events: list[dict[str, Any]] = []
        while limit is None or len(events) < limit:
            size = self.page_size
            if limit is not None:
                size = min(size, limit - len(events))
            params: Params = [
                ("where", where),
                ("order_by", order),
                ("limit", str(size)),
                ("offset", str(len(events))),
            ]
            page = get_json(self.client, self.url, params)
            batch = page.get("results") or []
            events.extend(batch)
            if len(batch) < size:
                break
        return events
