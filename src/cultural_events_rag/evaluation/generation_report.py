"""The report of the evaluation of the answers: a Markdown page, and a JSON
file of every answer."""

import json
from collections.abc import Sequence

from cultural_events_rag.evaluation.generation import (
    ABSTENTION,
    CORRECTNESS,
    FAITHFULNESS,
    JUDGED,
    PRECISION,
    RECALL,
    RELEVANCY,
    GenerationResult,
    summary,
)
from cultural_events_rag.evaluation.markdown import cell, table

NOTATION = (
    "For a question, $R$ is the set of its relevant events, $C$ the events "
    "found and given to the LLM, $A$ those its answer recommends. The first "
    "three metrics are exact; the last three are scored by an LLM judge "
    "(Ragas), for the questions with relevant events. Each mean is over the "
    "questions a metric applies to, counted beside it."
)
GLOSSARY = (
    (
        "Recommendation precision",
        r"$\dfrac{\lvert A \cap R \rvert}{\lvert A \rvert}$",
        (
            "The share of the events recommended that are relevant, for a "
            "question with at least one recommended."
        ),
    ),
    (
        "Recommendation recall",
        r"$\dfrac{\lvert A \cap R \cap C \rvert}{\lvert R \cap C \rvert}$",
        (
            "The share of the relevant events given to the LLM that it "
            "recommends, for a question with at least one given: what the "
            "answer keeps of what the search brought."
        ),
    ),
    (
        "Abstention",
        r"$\mathbb{1}\left[A = \emptyset\right]$",
        "1 when an out-of-scope question is answered without any event.",
    ),
    (
        "Faithfulness",
        (
            r"$\dfrac{\text{claims of the answer the events } C \text{ support}}"
            r"{\text{claims of the answer}}$"
        ),
        "1 when the answer invents nothing beyond the events given to the LLM.",
    ),
    (
        "Answer relevancy",
        r"$\cos(q, \hat{q})$",
        (
            "The question $\\hat{q}$ the judge writes back from the answer, "
            "compared with the question $q$ by the cosine of their embeddings: "
            "close to 1 when the answer addresses the question directly."
        ),
    ),
    (
        "Factual correctness",
        r"$\dfrac{2\,P\,R}{P + R}$",
        (
            "$P$: the share of the claims of the answer the reference answer "
            "supports; $R$: the share of the claims of the reference the answer "
            "gives. "
            "The reference picks a few events when many are relevant: an answer "
            "citing others loses points without being wrong."
        ),
    ),
)
LABELS = {
    PRECISION: "Recommendation precision",
    RECALL: "Recommendation recall",
    ABSTENTION: "Abstention (out of scope)",
    FAITHFULNESS: "Faithfulness",
    RELEVANCY: "Answer relevancy",
    CORRECTNESS: "Factual correctness",
}
ANSWER_WIDTH = 120


def _score(scores: dict[str, float], name: str) -> str:
    return cell(scores[name]) if name in scores else "-"


def _excerpt(answer: str) -> str:
    """Return the answer on one line, cut."""
    text = " ".join(answer.split()).replace("|", "/")
    return text if len(text) <= ANSWER_WIDTH else text[: ANSWER_WIDTH - 1] + "…"


def scores(results: list[GenerationResult]) -> list[str]:
    """Return the mean of each metric and the number of questions it applies to."""
    rows = [
        [LABELS[name], value, count]
        for name, (value, count) in summary(results).items()
    ]
    return table(["Metric", "Mean", "Questions"], rows)


def _judged(results: list[GenerationResult]) -> tuple[str, ...]:
    """Return the metrics of the judge, when it scored the answers."""
    return JUDGED if any(result.judged for result in results) else ()


def by_category(results: list[GenerationResult]) -> list[str]:
    """Return the metrics of the questions with relevant events, by category."""
    in_scope = [result for result in results if result.relevant]
    categories = list(dict.fromkeys(result.question.category for result in in_scope))
    names = (PRECISION, RECALL, *_judged(results))
    rows = []
    for category in categories:
        found = [result for result in in_scope if result.question.category == category]
        means = summary(found)
        rows.append(
            [
                f"{category} ({len(found)})",
                *(cell(means[name][0]) if name in means else "-" for name in names),
            ]
        )
    return table(["Category", *(LABELS[name] for name in names)], rows)


def each_question(results: list[GenerationResult]) -> list[str]:
    """Return, for each question with relevant events, the events given, those
    recommended and the scores."""
    judged = _judged(results)
    rows = []
    for result in results:
        if not result.relevant:
            continue
        metrics = result.metrics() | result.judged
        relevant_recommended = len(result.relevant.intersection(result.recommended))
        rows.append(
            [
                result.question.question,
                result.question.category,
                f"{len(result.relevant_given)} / {len(result.given)}",
                f"{relevant_recommended} / {len(result.recommended)}",
                _score(metrics, PRECISION),
                _score(metrics, RECALL),
                *(_score(metrics, name) for name in judged),
            ]
        )
    header = [
        "Question",
        "Category",
        "Relevant given",
        "Relevant recommended",
        "Precision",
        "Recall",
        *(LABELS[name] for name in judged),
    ]
    return table(header, rows)


def out_of_scope(results: list[GenerationResult]) -> list[str]:
    """Return, for each out-of-scope question, the events recommended and the answer."""
    rows = [
        [result.question.question, len(result.recommended), _excerpt(result.answer)]
        for result in results
        if not result.relevant
    ]
    return table(["Question", "Recommended", "Answer"], rows) if rows else []


def render(results: list[GenerationResult], context: Sequence[str]) -> str:
    """Return the Markdown report."""
    in_scope = sum(1 for result in results if result.relevant)
    out = len(results) - in_scope
    lines = ["# Evaluation of the answers", "", *(f"- {line}" for line in context), ""]
    lines += ["## How to read it", "", NOTATION, ""]
    header = ["Metric", "For a question", "What it says"]
    lines += [*table(header, GLOSSARY, centered=2), ""]
    lines += [f"## Scores ({len(results)} questions)", "", *scores(results), ""]
    lines += ["## By category", "", *by_category(results), ""]
    lines += [
        f"## Each question ({in_scope} with relevant events)",
        "",
        (
            "Relevant given: the relevant events among those given to the LLM. "
            "Relevant recommended: the relevant events among those its answer "
            "recommends. Every answer is in the JSON file beside this report."
        ),
        "",
        *each_question(results),
        "",
    ]
    if out:
        lines += [
            f"## Out-of-scope questions ({out})",
            "",
            *out_of_scope(results),
            "",
        ]
    return "\n".join(lines)


def to_json(results: list[GenerationResult]) -> str:
    """Return every answer by question: its text, the events it recommends and
    those the model was given."""
    answers = {
        result.question.id: {
            "answer": result.answer,
            "recommended": result.recommended,
            "given": result.given,
            "judged": result.judged,
        }
        for result in results
    }
    return json.dumps(answers, ensure_ascii=False, indent=2) + "\n"
