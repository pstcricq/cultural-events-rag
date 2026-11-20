"""The data files: the raw events as JSON, the processed events as JSON Lines,
one event per line."""

import json
from collections.abc import Sequence
from pathlib import Path

from cultural_events_rag.models import Event, RawEvents


def escape_line_separators(text: str) -> str:
    """U+2028 and U+2029 escaped: valid in JSON, but read as line breaks by
    editors and some tools. The content read back is the same."""
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def save_raw(raw: RawEvents, path: Path) -> None:
    """Write the raw events as one JSON document, by agenda uid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(raw, ensure_ascii=False, indent=2)
    path.write_text(escape_line_separators(content) + "\n", encoding="utf-8")


def load_raw(path: Path) -> RawEvents:
    """The raw events ``save_raw`` wrote, by agenda uid."""
    content = json.loads(path.read_text(encoding="utf-8"))
    return {int(uid): events for uid, events in content.items()}


def save_events(events: Sequence[Event], path: Path) -> None:
    """Write the events as JSON Lines, sorted by uid: two collections of the
    same events give the same file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(events, key=lambda event: int(event.uid))
    content = "".join(f"{event.model_dump_json()}\n" for event in ordered)
    path.write_text(escape_line_separators(content), encoding="utf-8")


def load_events(path: Path) -> list[Event]:
    """The events ``save_events`` wrote."""
    with path.open(encoding="utf-8") as file:
        return [Event.model_validate_json(line) for line in file if line.strip()]
