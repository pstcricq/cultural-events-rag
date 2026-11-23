"""cultural-events-rag index then status, end to end against a real
Elasticsearch with a fake embedding model."""

from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings


@pytest.fixture
def events_file(
    tmp_path: Path, settings: Settings, event: Event, monkeypatch: pytest.MonkeyPatch
) -> Path:
    path = tmp_path / "events.jsonl"
    save_events([event, event.model_copy(update={"uid": "2"})], path)
    for module in ("index", "status"):
        prefix = f"cultural_events_rag.cli.{module}"
        monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)
    monkeypatch.setattr("cultural_events_rag.cli.index.EVENTS_FILE", path)
    fake = DeterministicFakeEmbedding(size=16)
    monkeypatch.setattr("cultural_events_rag.cli.index.make_embeddings", lambda _: fake)
    return path


def test_status_before_any_index(
    events_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["status"]) == 1

    assert "run make index" in capsys.readouterr().err


def test_index_then_status(
    events_file: Path, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["index"]) == 0
    out = capsys.readouterr().out
    assert "Embedding: 100% (2/2 documents)" in out
    assert f"Index: {settings.elasticsearch_index} -> " in out

    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert ", 2 documents" in out
    assert "Settings: up to date" in out


def test_status_reports_an_index_built_otherwise(
    events_file: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["index"]) == 0
    monkeypatch.setattr("cultural_events_rag.indexing.build.CHUNK_SIZE", 500)

    assert main(["status"]) == 1

    assert "outdated: chunk_size: 1000 instead of 500" in capsys.readouterr().err
