"""Tests of the ``documents`` command on an events file: the summary, the
documents of one event, the exit code."""

from pathlib import Path

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.models import Event


@pytest.fixture
def events_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr("cultural_events_rag.cli.documents.EVENTS_FILE", path)
    return path


def test_documents_sums_up_the_documents_of_the_events(
    events_file: Path, event: Event, capsys: pytest.CaptureFixture[str]
) -> None:
    long = event.model_copy(
        update={"uid": "2", "long_description": "Une phrase. " * 200}
    )
    save_events([event, long], events_file)

    assert main(["documents"]) == 0

    out = capsys.readouterr().out
    assert "Events: 2 <- " in out
    assert "chunks: 1000 chars, 150 overlap" in out
    assert "Events split: 1" in out


def test_documents_prints_the_documents_of_one_event(
    events_file: Path, event: Event, capsys: pytest.CaptureFixture[str]
) -> None:
    save_events([event], events_file)

    assert main(["documents", "--uid", event.uid]) == 0

    out = capsys.readouterr().out
    assert f"--- {event.uid}-0" in out
    assert f"Titre : {event.title}" in out
    assert '"chunk_count": 1' in out


def test_documents_fails_on_an_unknown_event(
    events_file: Path, event: Event, capsys: pytest.CaptureFixture[str]
) -> None:
    save_events([event], events_file)

    assert main(["documents", "--uid", "0"]) == 1

    assert "no event 0" in capsys.readouterr().err


def test_documents_fails_without_events_file(
    events_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["documents"]) == 1

    assert "run make process" in capsys.readouterr().err
