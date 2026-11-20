"""The retry policy of the calls to an API, built on tenacity.

A transient failure (rate limit, server error, network error) is retried with
an exponential backoff, each retry logged. Any other error (invalid key, bad
request) fails at once.
"""

import logging
import time
from collections.abc import Callable

import httpx
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def is_transient(error: BaseException) -> bool:
    """Rate limit (429), server error (5xx) or network error: worth retrying."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return isinstance(error, httpx.TransportError)


def describe(error: BaseException) -> str:
    """A short label of the error for the logs: ``HTTP 429``, ``ConnectError``."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    return type(error).__name__


def make_retrying(
    action: str,
    retries: int = 5,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Retrying:
    """Retry ``action`` up to ``retries`` times, waiting ``backoff`` seconds,
    then twice as long each time. The last error is raised again as is.

    Usage: ``make_retrying("Request to api.openagenda.com")(function)``.
    """

    def log_retry(state: RetryCallState) -> None:
        error = state.outcome.exception() if state.outcome else None
        delay = state.next_action.sleep if state.next_action else 0.0
        logger.warning(
            "%s failed (%s): retrying in %.0fs (%d/%d)",
            action,
            describe(error) if error else "unknown error",
            delay,
            state.attempt_number,
            retries,
        )

    return Retrying(
        retry=retry_if_exception(is_transient),
        stop=stop_after_attempt(retries + 1),
        wait=wait_exponential(multiplier=backoff),
        sleep=sleep,
        before_sleep=log_retry,
        reraise=True,
    )
