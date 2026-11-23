"""The API end to end against a real Elasticsearch, with a fake embedding
model and a fake LLM: a question answered with the details of its events from
the index, the state of the index, and a rebuild run in the background."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from elasticsearch import Elasticsearch
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr

from cultural_events_rag.api.app import create_app
from cultural_events_rag.api.service import AssistantService
from cultural_events_rag.assistant import Assistant
from cultural_events_rag.elastic import index_alias
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)
LATER = timedelta(seconds=5)


def _answer(prompt: PromptValue) -> dict[str, Any]:
    """Every event given recommended."""
    uids = re.findall(r'<event uid="(\w+)">', prompt.to_string())
    return {"answer": "Une **visite** pour vous.", "event_uids": uids}


@pytest.fixture
def api(
    client: Elasticsearch, settings: Settings, event: Event
) -> Iterator[TestClient]:
    build_index(client, [event], FAKE, settings)
    settings = settings.model_copy(update={"admin_api_key": SecretStr("secret")})

    def load(_: Settings) -> Assistant:
        return Assistant(
            client, index_alias(settings), FAKE, None, RunnableLambda(_answer)
        )

    def rebuild(_: Settings, engine: Elasticsearch) -> int:
        # A new index, named after a later second than the first.
        build_index(engine, [event], FAKE, settings, now=datetime.now(UTC) + LATER)
        return 1

    service = AssistantService(settings, load=load, rebuild=rebuild)
    with TestClient(create_app(service)) as api:
        yield api


def test_a_question_answered_with_its_events(api: TestClient) -> None:
    response = api.post(
        "/ask",
        json={
            "question": "Une visite guidée au musée des Augustins en juin ?",
            "today": "2026-06-01",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Une visite pour vous."
    assert body["filters"]["venue"] == "Augustins"
    assert body["filters"]["date_from"] == "2026-06-01"
    [event] = body["events"]
    assert event["uid"] == "4154446"
    assert event["title"] == 'Visite guidée "Les peintres caravagesques en LSF"'
    assert event["venue"] == "Musée des Augustins"
    assert event["district"] == "Capitole / Arnaud Bernard / Carmes"
    assert (event["age_min"], event["age_max"]) == (None, None)
    assert event["dates"] == "dimanche 21 juin 2026, 14h30-15h30"
    assert event["next_slot"] == "2026-06-21T14:30:00+02:00"
    assert event["is_free"] is None


def test_the_health_and_the_index(api: TestClient) -> None:
    assert api.get("/health").json() == {"status": "ok", "detail": None}

    metadata = api.get("/metadata").json()

    assert metadata["city"] == "Toulouse"
    assert metadata["index"]["events"] == metadata["index"]["documents"] == 1
    assert metadata["rebuild"] == {
        "state": "idle",
        "started_at": None,
        "finished_at": None,
        "events": None,
        "detail": None,
    }


def test_a_rebuild_in_the_background(api: TestClient) -> None:
    before = api.get("/metadata").json()["index"]["index"]

    started = api.post("/rebuild", headers={"X-API-Key": "secret"})

    assert started.status_code == 202
    assert started.json()["state"] == "running"
    metadata = api.get("/metadata").json()
    assert metadata["rebuild"]["state"] == "done"
    assert metadata["rebuild"]["events"] == 1
    assert metadata["index"]["index"] != before  # the alias moved
    assert api.get("/health").json()["status"] == "ok"
