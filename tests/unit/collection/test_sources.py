"""The requests each source sends, its pagination, and the errors of a call:
retried when transient, a SourceError in the end."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from cultural_events_rag.collection.sources import (
    OpenAgendaSource,
    OpenDataSoftSource,
    get_json,
)
from cultural_events_rag.errors import SourceError
from cultural_events_rag.models import Agenda

SINCE = datetime(2025, 10, 15, tzinfo=UTC)

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, requests: list[httpx.Request]) -> httpx.Client:
    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    return httpx.Client(transport=httpx.MockTransport(recording_handler))


def no_sleep(_: float) -> None:
    pass


# --- get_json ----------------------------------------------------------------


def test_get_json_retries_on_server_error() -> None:
    responses = iter(
        [httpx.Response(503), httpx.Response(429), httpx.Response(200, json={})]
    )
    requests: list[httpx.Request] = []
    client = make_client(lambda _: next(responses), requests)

    assert get_json(client, "https://api.test", [], sleep=no_sleep) == {}
    assert len(requests) == 3


def test_get_json_gives_up_after_retries() -> None:
    requests: list[httpx.Request] = []
    client = make_client(lambda _: httpx.Response(500), requests)

    with pytest.raises(SourceError, match="HTTP 500"):
        get_json(client, "https://api.test", [], retries=2, sleep=no_sleep)
    assert len(requests) == 3


def test_get_json_does_not_retry_client_errors() -> None:
    requests: list[httpx.Request] = []
    client = make_client(lambda _: httpx.Response(403, text="invalid key"), requests)

    with pytest.raises(SourceError, match="HTTP 403"):
        get_json(client, "https://api.test", [], sleep=no_sleep)
    assert len(requests) == 1


def test_get_json_retries_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    requests: list[httpx.Request] = []
    with pytest.raises(SourceError, match="Network error"):
        get_json(make_client(handler, requests), "https://api.test", [], sleep=no_sleep)
    assert len(requests) == 4


# --- OpenAgendaSource --------------------------------------------------------


def openagenda_request(agenda: Agenda, upcoming: bool) -> httpx.Request:
    requests: list[httpx.Request] = []
    empty_page: dict[str, Any] = {"events": [], "after": None}
    client = make_client(lambda _: httpx.Response(200, json=empty_page), requests)
    OpenAgendaSource(client, "secret").fetch(agenda, "Toulouse", SINCE, 10, upcoming)
    return requests[0]


def test_openagenda_sends_key_and_filters(agenda: Agenda) -> None:
    request = openagenda_request(agenda, upcoming=True)

    assert request.url.path == "/v2/agendas/20289708/events"
    assert request.headers["key"] == "secret"
    assert "secret" not in str(request.url)
    assert request.url.params["adminLevel4[]"] == "Toulouse"
    assert request.url.params["size"] == "10"


def test_openagenda_upcoming_events_recently_updated_first(agenda: Agenda) -> None:
    params = openagenda_request(agenda, upcoming=True).url.params

    assert params.get_list("relative[]") == ["current", "upcoming"]
    assert params["sort"] == "updatedAt.desc"
    assert "timings[gte]" not in params


def test_openagenda_past_events_most_recent_first(agenda: Agenda) -> None:
    params = openagenda_request(agenda, upcoming=False).url.params

    assert params.get_list("relative[]") == ["passed"]
    assert params["timings[gte]"] == "2025-10-15T00:00:00+00:00"
    assert params["sort"] == "lastTiming.desc"


def test_openagenda_paginates_with_after(agenda: Agenda) -> None:
    pages = {
        None: {"events": [{"uid": 1}, {"uid": 2}], "after": [1, 2]},
        "2": {"events": [{"uid": 3}], "after": None},
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        after = request.url.params.get_list("after[]")
        return httpx.Response(200, json=pages[after[-1] if after else None])

    events = OpenAgendaSource(make_client(handler, requests), "k").fetch(
        agenda, "Toulouse", SINCE, limit=None, upcoming=True
    )

    assert [e["uid"] for e in events] == [1, 2, 3]
    assert requests[1].url.params.get_list("after[]") == ["1", "2"]


def test_openagenda_stops_at_limit(agenda: Agenda) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        size = int(request.url.params["size"])
        return httpx.Response(
            200, json={"events": [{"uid": i} for i in range(size)], "after": [1]}
        )

    events = OpenAgendaSource(make_client(handler, requests), "k").fetch(
        agenda, "Toulouse", SINCE, limit=5, upcoming=True
    )

    assert len(events) == 5
    assert len(requests) == 1


# --- OpenDataSoftSource ------------------------------------------------------


def test_opendatasoft_paginates_with_offset(agenda: Agenda) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        uids = range(offset, min(offset + 100, 150))
        results: list[dict[str, Any]] = [{"uid": str(i)} for i in uids]
        return httpx.Response(200, json={"total_count": 150, "results": results})

    events = OpenDataSoftSource(make_client(handler, requests)).fetch(
        agenda, "Toulouse", SINCE, limit=None, upcoming=True
    )

    assert len(events) == 150
    assert [r.url.params["offset"] for r in requests] == ["0", "100"]
    where = requests[0].url.params["where"]
    assert 'location_city="Toulouse"' in where
    assert 'originagenda_uid="20289708"' in where


@pytest.mark.parametrize(
    ("upcoming", "period", "order"),
    [
        (True, "lastdate_end >= now()", "updatedat desc"),
        (
            False,
            "lastdate_end < now() and lastdate_end >= date'2025-10-15'",
            "lastdate_end desc",
        ),
    ],
    ids=["upcoming", "past"],
)
def test_opendatasoft_period_and_order(
    agenda: Agenda, upcoming: bool, period: str, order: str
) -> None:
    requests: list[httpx.Request] = []
    empty: dict[str, Any] = {"total_count": 0, "results": []}
    client = make_client(lambda _: httpx.Response(200, json=empty), requests)

    OpenDataSoftSource(client).fetch(agenda, "Toulouse", SINCE, 10, upcoming)

    assert requests[0].url.params["where"].endswith(period)
    assert requests[0].url.params["order_by"] == order
