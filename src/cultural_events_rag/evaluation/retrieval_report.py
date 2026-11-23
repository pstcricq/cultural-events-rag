"""The report of the evaluation of the search: a Markdown page to read, every
configuration side by side and none put first, and a JSON file of every
ranking, to compare two runs question by question.

In each row of a table of scores, the best one is in bold, unless they are
all the same.
"""

import json
from collections.abc import Mapping, Sequence
from statistics import mean
from typing import Any

from cultural_events_rag.evaluation.dataset import EvalDataset
from cultural_events_rag.evaluation.markdown import bold_best, table
from cultural_events_rag.evaluation.retrieval import (
    CANDIDATES,
    SHOWN,
    QuestionResult,
    RetrievalConfig,
    in_scope,
    recall_at_k,
    summary,
    wins,
)

Results = Mapping[RetrievalConfig, Sequence[QuestionResult]]

METRICS = {
    f"hit@{SHOWN}": f"Hit@{SHOWN}",
    f"recall@{SHOWN}": f"Recall@{SHOWN}",
    f"precision@{SHOWN}": f"Precision@{SHOWN}",
    "mrr": "MRR",
    f"recall@{CANDIDATES}": f"Recall@{CANDIDATES}",
}

# Each metric of a question, its formula in LaTeX (rendered by GitHub and most
# Markdown viewers) and what it says. In a table: no | inside a formula, the
# absolute value written \lvert \rvert.
BOLD = (
    "In bold, the best score of each row. A row where every configuration "
    "scores the same has none: no configuration does better there."
)
NOTATION = (
    "For a question, $R$ is the set of its relevant events and $T_k$ the "
    "first $k$ events found. Each table gives the mean over the questions "
    "with relevant events."
)
_OVERLAP = r"\lvert R \cap T_{%d} \rvert"
_RELEVANT = r"\lvert R \rvert"
GLOSSARY = (
    (
        f"Hit@{SHOWN}",
        rf"$\mathbb{{1}}\left[R \cap T_{{{SHOWN}}} \neq \emptyset\right]$",
        f"1 when a relevant event is among the first {SHOWN}, 0 otherwise.",
    ),
    (
        f"Recall@{SHOWN}",
        rf"$\dfrac{{{_OVERLAP % SHOWN}}}{{\min({SHOWN}, {_RELEVANT})}}$",
        (
            f"The relevant events among the first {SHOWN}, out of the most "
            f"there can be: {SHOWN} relevant events first is a perfect answer, "
            "even to a question with 200 of them."
        ),
    ),
    (
        f"Precision@{SHOWN}",
        rf"$\dfrac{{{_OVERLAP % SHOWN}}}{{{SHOWN}}}$",
        (
            f"The share of the first {SHOWN} that is relevant: below 1 for a "
            f"question with fewer than {SHOWN} relevant events, "
            f"{1 / SHOWN:.2f} at most with one."
        ),
    ),
    (
        "MRR",
        r"$\dfrac{1}{r}$",
        (
            "$r$ is the rank of the first relevant event: 1 when it comes "
            "first, 0.5 when second, 0 without any. Its mean is the Mean "
            "Reciprocal Rank."
        ),
    ),
    (
        f"Recall@{CANDIDATES}",
        rf"$\dfrac{{{_OVERLAP % CANDIDATES}}}{{\min({CANDIDATES}, {_RELEVANT})}}$",
        (
            f"The same recall among the first {CANDIDATES}, the candidates of "
            "the reranker: it can only bring up an event among them, so it is "
            "the same with or without it."
        ),
    ),
)

TITLE_WIDTH = 40


def _score(value: float) -> str:
    """A score of the reranker: out of scope, it is often below 0.01."""
    return f"{value:.3f}"


def configurations(results: Results) -> list[str]:
    """The metrics of each configuration, the best of each metric in bold."""
    names = [config.name for config in results]
    summaries = [summary(found) for found in results.values()]
    columns = [bold_best([s[metric] for s in summaries]) for metric in METRICS]
    rows = [[name, *(column[i] for column in columns)] for i, name in enumerate(names)]
    return table(["Configuration", *METRICS.values()], rows)


def comparison(results: Results) -> list[str]:
    """For each pair of configurations, the questions where the one of the row
    does better than the one of the column on Recall@SHOWN."""
    configs = list(results)
    rows = [
        [
            config.name,
            *(
                "-" if other == config else wins(results[config], results[other])
                for other in configs
            ),
        ]
        for config in configs
    ]
    return table(["Better than →", *(config.name for config in configs)], rows)


def by_category(results: Results, metric: str) -> list[str]:
    """``metric`` by category of question, one column per configuration."""
    questions = in_scope(next(iter(results.values())))
    categories = list(dict.fromkeys(result.question.category for result in questions))
    rows = []
    for category in categories:
        values = [
            summary([r for r in in_scope(found) if r.question.category == category])[
                metric
            ]
            for found in results.values()
        ]
        count = sum(result.question.category == category for result in questions)
        rows.append([f"{category} ({count})", *bold_best(values)])
    return table(["Category", *(config.name for config in results)], rows)


def each_question(results: Results) -> list[str]:
    """Recall@SHOWN of each question with relevant events, by configuration."""
    first = in_scope(next(iter(results.values())))
    found = [in_scope(results[config]) for config in results]
    rows = []
    for i, result in enumerate(first):
        values = [
            recall_at_k(found_by[i].ranked, result.relevant, SHOWN)
            for found_by in found
        ]
        rows.append(
            [
                result.question.question,
                result.question.category,
                len(result.relevant),
                result.filters,
                *bold_best(values),
            ]
        )
    header = ["Question", "Category", "Relevant", "Filters", *(c.name for c in results)]
    return table(header, rows)


def _title(result: QuestionResult) -> str:
    if not result.titles:
        return "-"
    title = result.titles[0]
    return title if len(title) <= TITLE_WIDTH else title[: TITLE_WIDTH - 1] + "…"


def out_of_scope(results: Results) -> list[str]:
    """What comes first for each question without relevant event, by
    configuration; and the first score of the reranker, with and without
    relevant events: the lower out of scope, the better a threshold could tell
    them apart."""
    found = {
        config: [r for r in rs if not r.relevant] for config, rs in results.items()
    }
    first = next(iter(found.values()))
    if not first:
        return []
    rows = [
        [result.question.question, *(_title(found[config][i]) for config in results)]
        for i, result in enumerate(first)
    ]
    lines = table(["Question", *(config.name for config in results)], rows)

    reranked = [config for config in results if config.rerank]
    if reranked:
        first_scores: list[list[object]] = []
        for config in reranked:
            inside = [r.scores[0] for r in in_scope(results[config]) if r.scores]
            outside = [r.scores[0] for r in found[config] if r.scores]
            highest = max(outside)
            first_scores.append(
                [
                    config.name,
                    _score(mean(inside)),
                    _score(min(inside)),
                    _score(mean(outside)),
                    _score(highest),
                    f"{sum(score <= highest for score in inside)} / {len(inside)}",
                ]
            )
        header = [
            "Configuration",
            "With relevant events: mean",
            "lowest",
            "Out of scope: mean",
            "highest",
            "With relevant events, at most that highest",
        ]
        lines += [
            "",
            (
                "The first score of the reranker, between 0 and 1. A threshold "
                "that turns away every out-of-scope question would also turn "
                "away those of the last column:"
            ),
            "",
        ]
        lines += table(header, first_scores)
    return lines


def render(dataset: EvalDataset, results: Results, context: Sequence[str]) -> str:
    """The Markdown report."""
    questions = in_scope(next(iter(results.values())))
    out = len(dataset.questions) - len(questions)
    lines = ["# Evaluation of the search", "", *(f"- {line}" for line in context), ""]
    lines += ["## How to read it", "", NOTATION, ""]
    header = ["Metric", "For a question", "What it says"]
    lines += [*table(header, GLOSSARY, centered=2), "", BOLD, ""]
    lines += [
        f"## Configurations ({len(questions)} questions with relevant events)",
        "",
        *configurations(results),
        "",
    ]
    lines += [
        "## Question by question",
        "",
        (
            "The questions where the configuration of the row has a better "
            f"Recall@{SHOWN} than that of the column:"
        ),
        "",
        *comparison(results),
        "",
    ]
    lines += [
        f"## By category: Recall@{SHOWN}",
        "",
        *by_category(results, f"recall@{SHOWN}"),
    ]
    lines += ["", "## By category: MRR", "", *by_category(results, "mrr"), ""]
    lines += [
        f"## Each question: Recall@{SHOWN}",
        "",
        (
            "Filters: those the analysis found in the question, besides the "
            f"events from {dataset.reference_date} on that every search keeps."
        ),
        "",
        *each_question(results),
        "",
    ]
    if out:
        lines += [
            f"## Out-of-scope questions ({out}): the first event found",
            "",
            *out_of_scope(results),
            "",
        ]
    return "\n".join(lines)


def rankings(results: Results) -> dict[str, Any]:
    """Every ranking, by configuration then question: the uids found, best
    first."""
    return {
        config.name: {result.question.id: result.ranked for result in found}
        for config, found in results.items()
    }


def to_json(results: Results) -> str:
    """The rankings, one question per line: the diff of two runs shows the
    questions whose ranking changed."""

    def line(key: str, value: object) -> str:
        return f"{json.dumps(key, ensure_ascii=False)}: " + json.dumps(
            value, ensure_ascii=False
        )

    configs = [
        "  "
        + json.dumps(name, ensure_ascii=False)
        + ": {\n"
        + ",\n".join(f"    {line(id, ranked)}" for id, ranked in questions.items())
        + "\n  }"
        for name, questions in rankings(results).items()
    ]
    return "{\n" + ",\n".join(configs) + "\n}\n"
