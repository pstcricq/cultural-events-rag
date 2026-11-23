"""The Markdown of the reports of the evaluation: tables, their scores with
two decimals, the best of a row in bold."""

from collections.abc import Sequence


def cell(value: object) -> str:
    """A value as a table shows it: a score with two decimals."""
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def bold_best(values: Sequence[float]) -> list[str]:
    """The values as cells, the highest in bold unless all are the same: as
    shown, rounded, so that two cells that read the same are both in bold."""
    shown = [round(value, 2) for value in values]
    best = max(shown)
    alike = all(value == best for value in shown)
    return [
        f"**{cell(value)}**" if value == best and not alike else cell(value)
        for value in shown
    ]


def table(
    header: Sequence[str],
    rows: Sequence[Sequence[object]],
    centered: int = 0,
) -> list[str]:
    """A Markdown table, its first ``centered`` columns centered."""
    rules = [":---:" if i < centered else "---" for i in range(len(header))]
    lines = ["| " + " | ".join(header) + " |", "|" + "".join(f"{r}|" for r in rules)]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return lines
