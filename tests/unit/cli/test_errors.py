"""What each command says when a service fails, the services replaced: no
Elasticsearch, a refused password, an embedding request refused by Mistral;
and what index reports of the indices it replaced."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders, NodeConfig
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError
from langchain_core.embeddings import DeterministicFakeEmbedding
from pydantic import SecretStr

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.indexing.build import BuildReport
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

COMMANDS = ("status", "index")
CONNECTION = EngineConnectionError("connection refused")
REFUSED = AuthenticationException(
    "refused",
    ApiResponseMeta(
        status=401,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=NodeConfig("http", "127.0.0.1", 9200),
    ),
    {},
)
SETTINGS = Settings(
    _env_file=None,
    elasticsearch_url="http://127.0.0.1:9200",
    elasticsearch_index="events",
    elastic_user="elastic",
    elastic_password=SecretStr("password"),
    mistral_api_key=SecretStr("key"),
)


class Failing:
    """A client of Elasticsearch whose every request raises ``error``."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def __getattr__(self, name: str) -> Any:
        if name == "indices":
            return self

        def fail(*args: Any, **kwargs: Any) -> None:
            raise self.error

        return fail


def refusal(path: str) -> httpx.HTTPStatusError:
    """What a request to ``path`` of the Mistral API refused raises."""
    request = httpx.Request("POST", f"https://api.mistral.ai/v1/{path}")
    response = httpx.Response(401, request=request)
    return httpx.HTTPStatusError("unauthorized", request=request, response=response)


class Refused(DeterministicFakeEmbedding):
    """An embedding model whose every request Mistral refuses."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise refusal("embeddings")


@pytest.fixture(autouse=True)
def services(tmp_path: Path, event: Event, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every command with its settings, index with an events file, and an
    embedding model that never calls Mistral."""
    events = tmp_path / "events.jsonl"
    save_events([event], events)
    fake = DeterministicFakeEmbedding(size=4)
    for command in COMMANDS:
        monkeypatch.setattr(
            f"cultural_events_rag.cli.{command}.get_settings", lambda: SETTINGS
        )
    monkeypatch.setattr("cultural_events_rag.cli.index.EVENTS_FILE", events)
    monkeypatch.setattr("cultural_events_rag.cli.index.make_embeddings", lambda _: fake)


def _client(monkeypatch: pytest.MonkeyPatch, command: str, client: object) -> None:
    monkeypatch.setattr(
        f"cultural_events_rag.cli.{command}.make_elastic_client", lambda _: client
    )


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            CONNECTION,
            "FAIL no Elasticsearch at http://127.0.0.1:9200: run make docker-up",
        ),
        (REFUSED, "refused the password: check ELASTIC_PASSWORD"),
    ],
    ids=["no Elasticsearch", "password refused"],
)
def test_each_command_explains_an_elasticsearch_failure(
    command: str,
    error: Exception,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _client(monkeypatch, command, Failing(error))

    assert main([command]) == 1

    assert message in capsys.readouterr().err


def test_index_explains_a_refused_embedding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _client(monkeypatch, "index", Failing(CONNECTION))  # never reached
    monkeypatch.setattr(
        "cultural_events_rag.cli.index.make_embeddings", lambda _: Refused(size=4)
    )

    assert main(["index"]) == 1

    assert "FAIL embedding: " in (err := capsys.readouterr().err)
    assert "index unchanged" in err


def test_index_reports_the_indices_it_replaced_and_left(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _client(monkeypatch, "index", Failing(CONNECTION))
    report = BuildReport(
        index="events-2", documents=1, replaced=["events-1"], left=["events-1"]
    )
    monkeypatch.setattr(
        "cultural_events_rag.cli.index.build_index", lambda *_a, **_k: report
    )

    assert main(["index"]) == 0

    out, err = capsys.readouterr()
    assert "Replaced: events-1" in out
    assert "WARN old indices not deleted: events-1" in err
