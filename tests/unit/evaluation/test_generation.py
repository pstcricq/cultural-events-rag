"""The exact checks of the answers on hand-made results, and their report."""

import asyncio
import json
from dataclasses import replace

import pytest

from cultural_events_rag.evaluation.dataset import EvalQuestion
from cultural_events_rag.evaluation.generation import (
    GenerationResult,
    judge_answers,
    summary,
)
from cultural_events_rag.evaluation.generation_report import render, to_json


def question(id: str, relevant: list[str], category: str = "theme") -> EvalQuestion:
    return EvalQuestion.model_validate(
        {
            "id": id,
            "question": f"Question {id} ?",
            "category": category,
            "relevant": relevant,
        }
    )


def result(
    q: EvalQuestion, recommended: list[str], given: list[str]
) -> GenerationResult:
    return GenerationResult(
        question=q, answer=f"Réponse à {q.id}.", recommended=recommended, given=given
    )


# Relevant: a, b, c; the search gives a, b, x; the answer recommends a and x.
MIXED = result(question("q1", ["a", "b", "c"]), ["a", "x"], ["a", "b", "x"])
# Nothing relevant given: no recall; nothing recommended: no precision.
MISSED = result(question("q2", ["c"], "time"), [], ["x", "y"])
REFUSED = result(question("out", [], "out_of_scope"), [], ["x"])
ANSWERED = result(question("out2", [], "out_of_scope"), ["x"], ["x"])


def test_the_metrics_of_an_answer() -> None:
    assert MIXED.metrics() == {"precision": 0.5, "recall": 0.5}
    assert MISSED.metrics() == {}
    assert REFUSED.metrics() == {"abstention": 1.0}
    assert ANSWERED.metrics() == {"abstention": 0.0}


def test_each_mean_counts_the_questions_it_applies_to() -> None:
    assert summary([MIXED, MISSED, REFUSED, ANSWERED]) == {
        "precision": (0.5, 1),
        "recall": (0.5, 1),
        "abstention": (0.5, 2),
    }


def test_the_recall_counts_only_the_relevant_events_given() -> None:
    every = result(question("q3", ["a", "b"]), ["a"], ["a", "x"])

    assert every.metrics()["recall"] == 1.0  # b was never given


def test_the_report() -> None:
    long = result(question("out3", [], "out_of_scope"), [], [])
    long = GenerationResult(
        question=long.question, answer="Rien | " + "x" * 200, recommended=[], given=[]
    )
    report = render([MIXED, MISSED, REFUSED, long], ["Run: now"])

    assert "- Run: now" in report
    assert "| Metric | For a question | What it says |\n|:---:|:---:|---|" in report
    assert "| Recommendation precision | 0.50 | 1 |" in report
    assert "| Abstention (out of scope) | 1.00 | 2 |" in report
    assert "| theme (1) | 0.50 | 0.50 |" in report
    assert "| time (1) | - | - |" in report
    assert "| Question q1 ? | theme | 2 / 3 | 1 / 2 | 0.50 | 0.50 |" in report
    assert "| Question out ? | 0 | Réponse à out. |" in report
    # On one line, cut at 120 characters, no | to break the table.
    assert "| Rien / " + "x" * 112 + "… |" in report


@pytest.mark.parametrize("results", [[MIXED], [REFUSED]])
def test_the_answers_as_json(results: list[GenerationResult]) -> None:
    [(id, saved)] = json.loads(to_json(results)).items()

    assert id == results[0].question.id
    assert saved == {
        "answer": results[0].answer,
        "recommended": results[0].recommended,
        "given": results[0].given,
        "judged": results[0].judged,
    }


def test_the_report_with_the_judge() -> None:
    judged = replace(MIXED, judged={"faithfulness": 1.0, "answer_relevancy": 0.8})

    report = render([judged, MISSED, REFUSED], [])

    assert "| Faithfulness | 1.00 | 1 |" in report
    assert "| Answer relevancy | 0.80 | 1 |" in report
    assert "| theme (1) | 0.50 | 0.50 | 1.00 | 0.80 | - |" in report
    assert (
        "| Question q1 ? | theme | 2 / 3 | 1 / 2 | 0.50 | 0.50 | 1.00 | 0.80 | - |"
        in (report)
    )


class FakeJudge:
    """Scores each answer by its length; records the contexts it reads."""

    def __init__(self) -> None:
        self.read: list[tuple[str, list[str], str]] = []

    async def score(
        self, question: str, answer: str, contexts: list[str], reference: str
    ) -> dict[str, float]:
        self.read.append((question, list(contexts), reference))
        return {"faithfulness": 1.0}


def test_only_the_questions_with_relevant_events_are_judged() -> None:
    judge = FakeJudge()
    given = replace(MIXED, contexts=["Titre : a"])

    results = asyncio.run(judge_answers([given, REFUSED], judge))  # type: ignore[arg-type]

    assert [r.judged for r in results] == [{"faithfulness": 1.0}, {}]
    assert judge.read == [("Question q1 ?", ["Titre : a"], "")]
