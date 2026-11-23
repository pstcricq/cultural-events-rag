"""Tests of the ``index`` and ``status`` commands without Elasticsearch: the
progress lines, the logs, and a missing file or setting."""

import logging
from pathlib import Path

import pytest
from pydantic import SecretStr
from tokenizers import Tokenizer, models

from cultural_events_rag.cli import main
from cultural_events_rag.cli.index import Progress
from cultural_events_rag.cli.output import quiet_logs
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, module: str, **values: object) -> None:
    values = {
        "elasticsearch_url": "http://127.0.0.1:9200",
        "elasticsearch_index": "events",
        "elastic_user": "elastic",
        **values,
    }
    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]
    monkeypatch.setattr(
        f"cultural_events_rag.cli.{module}.get_settings", lambda: settings
    )


def test_progress_prints_a_line_per_tenth(capsys: pytest.CaptureFixture[str]) -> None:
    progress = Progress()
    for done in (3, 10, 15, 50, 100):
        progress(done, 100)

    assert capsys.readouterr().out.splitlines() == [
        "Embedding:  10% (10/100 documents)",
        "Embedding:  50% (50/100 documents)",
        "Embedding: 100% (100/100 documents)",
    ]


@pytest.mark.parametrize(
    "name", ["elastic_transport.transport", "langchain_mistralai.embeddings"]
)
def test_a_failed_request_logs_no_traceback(
    name: str, caplog: pytest.LogCaptureFixture
) -> None:
    quiet_logs()

    logging.getLogger(name).warning("Retrying request after failure")

    assert caplog.records == []


def test_index_fails_without_events_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _settings(monkeypatch, "index")
    monkeypatch.setattr("cultural_events_rag.cli.index.EVENTS_FILE", tmp_path / "none")

    assert main(["index"]) == 1

    assert "run make process" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("values", "missing"),
    [
        ({"mistral_api_key": SecretStr("key")}, "ELASTIC_PASSWORD"),
        ({"elastic_password": SecretStr("password")}, "MISTRAL_API_KEY"),
        (
            {
                "elastic_password": SecretStr("password"),
                "mistral_api_key": SecretStr("key"),
                "elasticsearch_index": None,
            },
            "ELASTICSEARCH_INDEX",
        ),
    ],
)
def test_index_names_the_missing_setting(
    values: dict[str, SecretStr | None],
    missing: str,
    event: Event,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events_file = tmp_path / "events.jsonl"
    save_events([event], events_file)
    _settings(monkeypatch, "index", **values)
    monkeypatch.setattr("cultural_events_rag.cli.index.EVENTS_FILE", events_file)
    # A tokenizer of one word, made here: the Hugging Face cache is not read.
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    monkeypatch.setattr(
        "cultural_events_rag.mistral.Tokenizer.from_pretrained", lambda *_: tokenizer
    )

    assert main(["index"]) == 1

    assert f"{missing} is not set" in capsys.readouterr().err


def test_status_names_the_missing_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _settings(monkeypatch, "status")

    assert main(["status"]) == 1

    assert "ELASTIC_PASSWORD is not set" in capsys.readouterr().err
