"""Tests of the API client on a fake API (httpx.MockTransport): its requests,
its responses, and its errors."""

import json
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest

from cultural_events_rag.ui.client import ApiClient, ApiError

ASKED = {
    "question": "Un concert ?",
    "today": "2026-11-19",
    "answer": "Je vous recommande ce concert.",
    "filters": {"date_from": "2026-11-19"},
    "events": [
        {
            "uid": "1",
            "title": "Concert",
            "venue": "Le Bikini",
            "address": None,
            "district": None,
            "age_min": None,
            "age_max": None,
            "dates": "samedi 21 novembre 2026, 20h30-23h00",
            "next_slot": "2026-11-21T20:30:00+01:00",
            "is_free": None,
            "url": None,
        }
    ],
}

Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler) -> ApiClient:
    return ApiClient("http://api", transport=httpx.MockTransport(handler))


def answering(status: int, body: Any) -> Handler:
    return lambda request: httpx.Response(status, json=body)


def failing(error: type[httpx.TransportError]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("down", request=request)

    return handler


def test_a_question_is_sent_without_a_day_by_default() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=ASKED)

    response = client(handler).ask("Un concert ?")

    assert sent[0].method == "POST"
    assert sent[0].url.path == "/ask"
    assert json.loads(sent[0].content) == {"question": "Un concert ?"}
    assert response.answer == "Je vous recommande ce concert."
    assert response.events[0].is_free is None


def test_a_question_is_sent_with_the_day_chosen() -> None:
    bodies: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=ASKED)

    client(handler).ask("Un concert ?", date(2026, 10, 19))

    assert bodies == [{"question": "Un concert ?", "today": "2026-10-19"}]


def test_the_health_of_an_unavailable_assistant_is_an_answer() -> None:
    body = {"status": "unavailable", "detail": "no index"}

    health = client(answering(503, body)).health()

    assert health.status == "unavailable"
    assert health.detail == "no index"


def test_the_health_of_a_ready_assistant() -> None:
    assert client(answering(200, {"status": "ok"})).health().status == "ok"


def test_the_metadata_are_read() -> None:
    body = {
        "city": "Toulouse",
        "index": None,
        "embedding_model": "mistral-embed",
        "search_mode": "hybrid",
        "search_k": 5,
        "rerank_model": None,
        "llm_model": "ministral-14b-latest",
        "llm_requests_per_minute": 2,
        "rebuild": {"state": "idle"},
    }

    metadata = client(answering(200, body)).metadata()

    assert metadata.city == "Toulouse"
    assert metadata.index is None


@pytest.mark.parametrize(
    ("status", "body", "detail"),
    [
        (503, {"detail": "no index"}, "no index"),
        (502, {"detail": "Mistral failed"}, "Mistral failed"),
        (
            422,
            {"detail": [{"msg": "too long"}, {"msg": "missing"}]},
            "too long; missing",
        ),
        (422, {"detail": ["odd"]}, "odd"),
    ],
)
def test_a_refusal_raises_its_code_and_detail(
    status: int, body: Any, detail: str
) -> None:
    with pytest.raises(ApiError) as raised:
        client(answering(status, body)).ask("Un concert ?")

    assert raised.value.status_code == status
    assert raised.value.detail == detail
    assert not raised.value.timed_out


def test_an_error_not_from_the_api_gives_its_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad gateway")

    with pytest.raises(ApiError) as raised:
        client(handler).ask("Un concert ?")

    assert raised.value.detail == "Bad gateway"


def test_an_error_without_body_gives_its_reason() -> None:
    with pytest.raises(ApiError) as raised:
        client(lambda request: httpx.Response(500)).metadata()

    assert raised.value.detail == "Internal Server Error"


def test_an_unreachable_api() -> None:
    with pytest.raises(ApiError) as raised:
        client(failing(httpx.ConnectError)).health()

    assert raised.value.status_code is None
    assert not raised.value.timed_out
    assert "http://api unreachable (ConnectError)" == raised.value.detail


def test_an_api_too_slow() -> None:
    with pytest.raises(ApiError) as raised:
        client(failing(httpx.ReadTimeout)).ask("Un concert ?")

    assert raised.value.status_code is None
    assert raised.value.timed_out
