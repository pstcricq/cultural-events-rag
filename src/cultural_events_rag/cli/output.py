"""The output of the ``cultural-events-rag`` command."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from cultural_events_rag.logs import quiet_libraries
from cultural_events_rag.paths import ROOT


def question(text: str) -> str:
    """Return a question as typed; refuse one without any word."""
    if not text.strip():
        raise argparse.ArgumentTypeError('empty: with make, Q="..."')
    return text


def shown(path: Path) -> str:
    """Return a path relative to the root of the checkout when it is inside it."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def quiet_logs() -> None:
    """Send the logs to stdout and quiet the libraries."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    quiet_libraries()


def duration(seconds: float) -> str:
    """Return a duration as a person reads it: "40 s", "3 min", "2 h 40 min"."""
    if seconds < 60:
        return f"{seconds:.0f} s"
    hours, minutes = divmod(round(seconds / 60), 60)
    if not hours:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min" if minutes else f"{hours} h"


def aligned(table: Sequence[str], bold: bool = False) -> list[str]:
    """Return a Markdown table aligned for a terminal: numbers to the right, a
    rule under the header, its bold cells in ANSI bold when ``bold``."""
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table
        if not set(line) <= set("|-: ")  # rule under the header
    ]
    texts = [[cell.strip("*") for cell in row] for row in rows]
    widths = [max(len(row[i]) for row in texts) for i in range(len(texts[0]))]
    lines = []
    for row, text in zip(rows, texts, strict=True):
        cells = []
        for i, (cell, value) in enumerate(zip(row, text, strict=True)):
            padded = value.ljust(widths[i]) if i == 0 else value.rjust(widths[i])
            if bold and cell.startswith("**"):
                padded = f"\033[1m{padded}\033[0m"
            cells.append(padded)
        lines.append("  ".join(cells).rstrip())
    rule = "-" * (sum(widths) + 2 * (len(widths) - 1))
    return [lines[0], rule, *lines[1:]]


def confirm(question: str) -> bool:
    """Ask a yes or no ``question`` on the terminal; no by default, and without
    a terminal."""
    try:
        answer = input(f"{question} [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes", "o", "oui")
