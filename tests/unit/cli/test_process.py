"""cultural-events-rag process, end to end on a raw file written for the test:
the events file it writes, what it prints, its exit code."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_raw
from cultural_events_rag.constants import CULTURAL_AGENDAS
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """No key, so the OpenDataSoft raw file; both files in tmp_path."""
    settings = Settings(_env_file=None)
    monkeypatch.setattr(
        "cultural_events_rag.cli.process.get_settings", lambda: settings
    )
    monkeypatch.setattr("cultural_events_rag.cli.process.RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(
        "cultural_events_rag.cli.process.EVENTS_FILE", tmp_path / "events.jsonl"
    )
    return tmp_path


def test_process_writes_the_events_of_the_common_format(
    data_dir: Path, ods_record: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    begin = datetime.now(UTC) + timedelta(days=1)
    timings = [
        {"begin": begin.isoformat(), "end": (begin + timedelta(hours=1)).isoformat()}
    ]
    upcoming = ods_record | {"timings": json.dumps(timings)}
    save_raw(
        {CULTURAL_AGENDAS[0].uid: [upcoming, upcoming | {"location_city": "Blagnac"}]},
        data_dir / "raw" / "opendatasoft.json",
    )

    assert main(["process"]) == 0

    lines = (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [Event.model_validate_json(line).uid for line in lines] == ["4154446"]
    out = capsys.readouterr().out
    assert "Raw: 2 events <- " in out
    assert "Dropped: out_of_area: 1" in out
    assert "Kept: 1 events -> " in out


def test_process_fails_without_raw_file(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["process"]) == 1

    assert "run make fetch" in capsys.readouterr().err
    assert not (data_dir / "events.jsonl").exists()
