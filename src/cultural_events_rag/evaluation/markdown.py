"""The Markdown tables of the reports: scores with two decimals, the best of a
row in bold."""

from collections.abc import Sequence


def cell(value: object) -> str:
    """Return a value as a table cell: a score with two decimals."""
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def bold_best(values: Sequence[float]) -> list[str]:
    """Return the values as cells, the highest in bold unless all are equal,
    compared as shown, rounded."""
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
    """Return a Markdown table, its first ``centered`` columns centered."""
    rules = [":---:" if i < centered else "---" for i in range(len(header))]
    lines = ["| " + " | ".join(header) + " |", "|" + "".join(f"{r}|" for r in rules)]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return lines
