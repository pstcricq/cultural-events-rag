"""The raw file read back as written, the unicode line separators escaped."""

import json
from pathlib import Path

from cultural_events_rag.collection.files import load_raw, save_raw
from cultural_events_rag.models import RawEvents


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
