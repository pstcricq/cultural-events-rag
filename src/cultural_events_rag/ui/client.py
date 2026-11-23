"""The client of the REST API the web interface goes through.

The interface never calls the RAG code: it asks the API, as any front end
would. The answers are read with the schemas of the API, the one contract
both sides keep to.
"""

from datetime import date
from typing import Any

import httpx

from cultural_events_rag.api.schemas import (
    AskResponse,
    HealthResponse,
    MetadataResponse,
)

# An answer waits its turn under the quota of the Mistral plan (30 s on the
# free plan), behind the questions asked before it, then the reranking (about
# 10 s under Docker): two minutes leave room for a short queue.
TIMEOUT = 120.0


class ApiError(Exception):
    """The API refused the request (its status code and its detail), or did
    not answer: unreachable (status_code None) or too slow (timed_out)."""

    def __init__(
        self, status_code: int | None, detail: str, *, timed_out: bool = False
    ) -> None:
        super().__init__(detail if status_code is None else f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        self.timed_out = timed_out


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def ask(self, question: str, today: date | None = None) -> AskResponse:
        """The answer to ``question``, asked on ``today`` (today in the city by
        default)."""
        body: dict[str, Any] = {"question": question}
        if today is not None:
            body["today"] = today.isoformat()
        response = self._send("POST", "/ask", json=body)
        return AskResponse.model_validate(_json(response))

    def metadata(self) -> MetadataResponse:
        return MetadataResponse.model_validate(_json(self._send("GET", "/metadata")))

    def health(self) -> HealthResponse:
        """Whether the assistant can answer: a 503 is an answer too, with its
        reason."""
        response = self._send("GET", "/health")
        if response.status_code == httpx.codes.SERVICE_UNAVAILABLE:
            return HealthResponse.model_validate(response.json())
        return HealthResponse.model_validate(_json(response))

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ApiError(
                None, f"no answer from {self.base_url} in time", timed_out=True
            ) from exc
        except httpx.TransportError as exc:
            raise ApiError(
                None, f"{self.base_url} unreachable ({type(exc).__name__})"
            ) from exc


def _json(response: httpx.Response) -> Any:
    """The body of a success, or the error the API gave."""
    if response.is_error:
        raise ApiError(response.status_code, error_detail(response))
    return response.json()


def error_detail(response: httpx.Response) -> str:
    """The ``detail`` of an error of the API: one message per field for a
    validation error (422)."""
    try:
        detail = response.json()["detail"]
    except (ValueError, KeyError, TypeError):
        return response.text or response.reason_phrase
    if isinstance(detail, list):
        return "; ".join(
            str(error.get("msg", error)) if isinstance(error, dict) else str(error)
            for error in detail
        )
    return str(detail)
