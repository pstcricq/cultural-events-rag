"""Tests of the benchmark questions: their rules, and the versioned ones valid
against the frozen events."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from cultural_events_rag.collection.files import load_events
from cultural_events_rag.evaluation.dataset import (
    EvalDataset,
    EvalQuestion,
    load_dataset,
)
from cultural_events_rag.paths import BENCHMARK_EVENTS, BENCHMARK_QUESTIONS


def question(**values: Any) -> dict[str, Any]:
    return {"id": "q1", "question": "Un concert ?", "category": "theme"} | values


def test_only_an_out_of_scope_question_has_no_relevant_event() -> None:
    with pytest.raises(ValidationError, match="only an out_of_scope question"):
        EvalQuestion.model_validate(question(relevant=[]))
    with pytest.raises(ValidationError, match="only an out_of_scope question"):
        EvalQuestion.model_validate(question(category="out_of_scope", relevant=["1"]))

    assert EvalQuestion.model_validate(question(category="out_of_scope")).relevant == []


def test_each_question_has_an_id_of_its_own() -> None:
    with pytest.raises(ValidationError, match="an id of its own"):
        EvalDataset.model_validate(
            {
                "reference_date": "2026-10-19",
                "relevant_status": "draft",
                "questions": [question(relevant=["1"]), question(relevant=["2"])],
            }
        )


def test_the_relevant_events_missing_are_listed() -> None:
    dataset = EvalDataset(
        reference_date=date(2026, 10, 19),
        relevant_status="draft",
        questions=[EvalQuestion.model_validate(question(relevant=["1", "2"]))],
    )

    assert dataset.unknown_uids({"1"}) == ["q1: 2"]


def test_the_committed_benchmark_is_valid() -> None:
    dataset = load_dataset(BENCHMARK_QUESTIONS)
    uids = {event.uid for event in load_events(BENCHMARK_EVENTS)}

    assert len(dataset.questions) == 50
    assert dataset.reference_date == date(2026, 10, 19)
    assert dataset.relevant_status == "validated"
    assert len(uids) == 1850
    assert dataset.unknown_uids(uids) == []
