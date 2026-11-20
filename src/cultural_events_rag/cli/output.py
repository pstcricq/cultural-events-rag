"""What the cultural-events-rag command prints."""

from pathlib import Path

from cultural_events_rag.paths import ROOT


def shown(path: Path) -> str:
    """A path as a line names it, from the root of the checkout when it is
    inside it."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
