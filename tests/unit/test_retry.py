"""Transient errors retried with an exponential backoff, each retry logged;
any other error raised at once."""

import logging

import httpx
import pytest

from cultural_events_rag.retry import describe, is_transient, make_retrying


def http_error(
    status: int, headers: dict[str, str] | None = None
) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.openagenda.com/v2/agendas/1/events")
    response = httpx.Response(status, headers=headers)
    return httpx.HTTPStatusError("error", request=request, response=response)


class Flaky:
    """Callable failing with the given errors first, then returning "ok"."""

    def __init__(self, errors: list[Exception]) -> None:
        self.errors = list(errors)
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (http_error(429), True),
        (http_error(500), True),
        (http_error(503), True),
        (httpx.ConnectError("down"), True),
        (httpx.ReadTimeout("slow"), True),
        (http_error(400), False),
        (http_error(401), False),
        (http_error(403), False),
        (ValueError("bug"), False),
    ],
)
def test_is_transient(error: Exception, transient: bool) -> None:
    assert is_transient(error) is transient


def test_describe() -> None:
    assert describe(http_error(429)) == "HTTP 429"
    assert describe(http_error(403)) == "HTTP 403"
    assert describe(httpx.ConnectError("down")) == "ConnectError"


def test_transient_errors_retried_with_exponential_backoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    waits: list[float] = []
    flaky = Flaky([http_error(429), http_error(503), httpx.ConnectError("down")])

    with caplog.at_level(logging.WARNING):
        result = make_retrying("Request", retries=5, backoff=2.0, sleep=waits.append)(
            flaky
        )

    assert result == "ok"
    assert waits == [2.0, 4.0, 8.0]
    assert caplog.messages == [
        "Request failed (HTTP 429): retrying in 2s (1/5)",
        "Request failed (HTTP 503): retrying in 4s (2/5)",
        "Request failed (ConnectError): retrying in 8s (3/5)",
    ]


def test_other_errors_fail_immediately() -> None:
    flaky = Flaky([http_error(401)])

    with pytest.raises(httpx.HTTPStatusError):
        make_retrying("Request", sleep=lambda _: None)(flaky)
    assert flaky.calls == 1


def test_last_error_reraised_after_the_last_retry() -> None:
    flaky = Flaky([http_error(503)] * 4)

    with pytest.raises(httpx.HTTPStatusError) as raised:
        make_retrying("Request", retries=2, sleep=lambda _: None)(flaky)
    assert raised.value.response.status_code == 503
    assert flaky.calls == 3
