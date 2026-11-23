"""The data files: the raw events as JSON, the processed events as JSON Lines."""

import json
from collections.abc import Sequence
from pathlib import Path

from cultural_events_rag.models import Event, RawEvents


def escape_line_separators(text: str) -> str:
    """Escape the line separators U+2028 and U+2029, valid in JSON but read as
    line breaks by some tools. The content read back is unchanged."""
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def save_raw(raw: RawEvents, path: Path) -> None:
    """Write the raw events as one JSON document, by agenda uid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(raw, ensure_ascii=False, indent=2)
    path.write_text(escape_line_separators(content) + "\n", encoding="utf-8")


def load_raw(path: Path) -> RawEvents:
    """Read the raw events ``save_raw`` wrote, by agenda uid."""
    content = json.loads(path.read_text(encoding="utf-8"))
    return {int(uid): events for uid, events in content.items()}


def save_events(events: Sequence[Event], path: Path) -> None:
    """Write the events as JSON Lines, sorted by uid."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(events, key=lambda event: int(event.uid))
    content = "".join(f"{event.model_dump_json()}\n" for event in ordered)
    path.write_text(escape_line_separators(content), encoding="utf-8")


def load_events(path: Path) -> list[Event]:
    """Read the events ``save_events`` wrote."""
    with path.open(encoding="utf-8") as file:
        return [Event.model_validate_json(line) for line in file if line.strip()]
