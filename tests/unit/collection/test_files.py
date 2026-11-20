"""The raw file and the events file read back as written, sorted, the unicode
line separators escaped."""

import json
from pathlib import Path
from typing import Any

from cultural_events_rag.collection.files import (
    load_events,
    load_raw,
    save_events,
    save_raw,
)
from cultural_events_rag.collection.parsing import parse_opendatasoft_record
from cultural_events_rag.models import Agenda, Event, RawEvents


def test_the_raw_events_read_back_by_agenda_uid(tmp_path: Path) -> None:
    raw: RawEvents = {20289708: [{"uid": 1}], 36779486: []}
    path = tmp_path / "raw" / "fake.json"

    save_raw(raw, path)

    assert load_raw(path) == raw


def test_the_raw_file_escapes_the_unicode_line_separators(tmp_path: Path) -> None:
    raw: RawEvents = {1: [{"text": "avant après fin"}]}
    path = tmp_path / "fake.json"

    save_raw(raw, path)

    content = path.read_text(encoding="utf-8")
    assert " " not in content and " " not in content
    assert json.loads(content) == {"1": [{"text": "avant après fin"}]}


def test_the_events_are_written_one_per_line_sorted_by_uid(
    ods_record: dict[str, Any], agenda: Agenda, tmp_path: Path
) -> None:
    events = [
        parse_opendatasoft_record(ods_record | {"uid": uid}, agenda)
        for uid in ("20", "3")
    ]
    path = tmp_path / "processed" / "events.jsonl"

    save_events(events, path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [Event.model_validate_json(line).uid for line in lines] == ["3", "20"]


def test_the_events_file_escapes_the_unicode_line_separators(
    ods_record: dict[str, Any], agenda: Agenda, tmp_path: Path
) -> None:
    record = ods_record | {"keywords_fr": ["jazz live"]}
    event = parse_opendatasoft_record(record, agenda)
    path = tmp_path / "events.jsonl"

    save_events([event], path)

    content = path.read_text(encoding="utf-8")
    assert " " not in content
    assert Event.model_validate_json(content).keywords == ["jazz live"]


def test_the_events_read_back_as_written(
    ods_record: dict[str, Any], agenda: Agenda, tmp_path: Path
) -> None:
    events = [
        parse_opendatasoft_record(ods_record | {"uid": uid}, agenda)
        for uid in ("1", "2")
    ]
    path = tmp_path / "events.jsonl"
    save_events(events, path)

    assert load_events(path) == events
