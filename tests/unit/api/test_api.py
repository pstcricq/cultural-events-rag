"""Tests of the API answers when something is missing or fails, its service
replaced: no assistant, a refused key, Mistral or Elasticsearch failing, a
rebuild already running or failing."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from elastic_transport import ConnectionError as TransportConnectionError
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cultural_events_rag.api.app import create_app
from cultural_events_rag.api.service import AssistantService, rebuild_index
from cultural_events_rag.assistant import Assistant
from cultural_events_rag.collection.process import ProcessReport
from cultural_events_rag.errors import (
    GenerationError,
    MissingSettingError,
    SourceError,
)
from cultural_events_rag.generation.answer import Answer
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

SETTINGS = Settings(_env_file=None, admin_api_key=SecretStr("secret"), max_events="all")
ADMIN = {"X-API-Key": "secret"}


def missing_key(settings: Settings) -> Assistant:
    raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")


def loaded(settings: Settings) -> Assistant:
    nothing: Any = None  # never reached: the service is replaced
    return Assistant(nothing, "events", None, None, nothing)


class Stub(AssistantService):
    """A service whose index is fine, its questions failing with ``error``."""

    def __init__(self, error: Exception, **kwargs: Any) -> None:
        super().__init__(SETTINGS, load=loaded, **kwargs)
        self.error = error

    def problem(self) -> str | None:
        return None

    def ask(self, question: str, today: date) -> Answer:
        raise self.error


def test_without_assistant_every_route_says_why() -> None:
    with TestClient(create_app(AssistantService(SETTINGS, load=missing_key))) as api:
        health = api.get("/health")
        asked = api.post("/ask", json={"question": "Un concert ?"})
        metadata = api.get("/metadata")
        rebuild = api.post("/rebuild", headers=ADMIN)

    assert health.status_code == 503
    assert health.json() == {
        "status": "unavailable",
        "detail": "MISTRAL_API_KEY is not set: add it to .env",
    }
    assert asked.status_code == metadata.status_code == rebuild.status_code == 503
    assert "MISTRAL_API_KEY" in metadata.json()["detail"]


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_an_empty_or_too_long_question_is_refused(question: str) -> None:
    with TestClient(create_app(Stub(GenerationError("never")))) as api:
        assert api.post("/ask", json={"question": question}).status_code == 422


def _refused() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return httpx.HTTPStatusError("rate limited", request=request, response=response)


@pytest.mark.parametrize(
    ("error", "code", "detail"),
    [
        (_refused(), 502, "Mistral failed: HTTP 429"),
        (GenerationError("no structured answer"), 502, "no structured answer"),
        (TransportConnectionError("refused"), 503, "Elasticsearch failed"),
    ],
    ids=["mistral", "generation", "elasticsearch"],
)
def test_a_failing_service_gives_its_code(
    error: Exception, code: int, detail: str
) -> None:
    with TestClient(create_app(Stub(error))) as api:
        response = api.post("/ask", json={"question": "Un concert ?"})

    assert response.status_code == code
    assert detail in response.json()["detail"]


class Unreachable(Stub):
    """A service whose Elasticsearch cannot be reached."""

    def problem(self) -> str | None:
        raise TransportConnectionError("Failed to resolve 'elasticsearch'")


def test_health_logs_why_elasticsearch_fails(caplog: pytest.LogCaptureFixture) -> None:
    with TestClient(create_app(Unreachable(GenerationError("never")))) as api:
        health = api.get("/health")

    assert health.status_code == 503
    # The cause in the logs, for the operator; its kind only in the answer.
    assert health.json()["detail"] == "Elasticsearch failed: ConnectionError"
    assert "Failed to resolve 'elasticsearch'" in caplog.text


@pytest.mark.parametrize(
    ("settings", "headers", "code"),
    [
        (Settings(_env_file=None), ADMIN, 403),  # no ADMIN_API_KEY: turned off
        (Settings(_env_file=None, admin_api_key=SecretStr("")), ADMIN, 403),
        (SETTINGS, {}, 401),
        (SETTINGS, {"X-API-Key": "wrong"}, 401),
    ],
    ids=["unset", "empty", "missing", "wrong"],
)
def test_the_rebuild_needs_the_admin_key(
    settings: Settings, headers: dict[str, str], code: int
) -> None:
    service = AssistantService(settings, load=loaded)

    with TestClient(create_app(service)) as api:
        assert api.post("/rebuild", headers=headers).status_code == code


def test_one_rebuild_at_a_time() -> None:
    service = Stub(GenerationError("never"))

    with TestClient(create_app(service)) as api:
        service.start_rebuild()  # one running
        response = api.post("/rebuild", headers=ADMIN)

    assert response.status_code == 409
    assert service.rebuild_state.state == "running"


def test_a_failed_rebuild_is_kept_and_frees_the_next() -> None:
    def failing(settings: Settings, client: Any) -> int:
        raise RuntimeError("Open Agenda refused")

    service = Stub(GenerationError("never"), rebuild=failing)

    with TestClient(create_app(service)) as api:
        assert api.post("/rebuild", headers=ADMIN).status_code == 202

    state = service.rebuild_state
    assert state.state == "failed"
    assert state.detail == "Open Agenda refused"
    assert state.finished_at is not None
    service.start_rebuild()  # the lock was released


def test_a_rebuild_fetches_processes_and_indexes(
    event: Event, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = "cultural_events_rag.api.service"
    built: list[Any] = []
    monkeypatch.setattr(f"{prefix}.RAW_DIR", tmp_path)
    monkeypatch.setattr(f"{prefix}.EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(
        f"{prefix}.select_source", lambda settings, http: SimpleNamespace(name="ods")
    )
    monkeypatch.setattr(f"{prefix}.fetch_agendas", lambda *_: {"1": [{"uid": 1}]})
    monkeypatch.setattr(f"{prefix}.make_embeddings", lambda _: "embeddings")
    monkeypatch.setattr(
        f"{prefix}.build_index", lambda client, events, *_: built.append(events)
    )
    reports = iter([ProcessReport(events=[event]), ProcessReport()])
    monkeypatch.setattr(f"{prefix}.process_events", lambda *_: next(reports))

    assert rebuild_index(SETTINGS, "client") == 1  # type: ignore[arg-type]
    assert built == [[event]]
    assert (tmp_path / "ods.json").is_file()
    assert (tmp_path / "events.jsonl").is_file()
    with pytest.raises(SourceError, match="the index served is kept"):
        rebuild_index(SETTINGS, "client")  # type: ignore[arg-type]
    assert len(built) == 1
