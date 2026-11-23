"""The annotated questions of the benchmark (``data/benchmark/questions.json``),
shared by the evaluation of the search and that of the answers.

For each question, a human listed the relevant events (their uids) and wrote a
reference answer, both judged as of a reference date: "ce week-end" keeps the
same meaning at each run.
"""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Category = Literal[
    "theme", "audience", "practical", "place", "time", "entity", "out_of_scope"
]
Status = Literal["draft", "validated"]


class EvalQuestion(BaseModel):
    """A question, the events relevant to it, and the answer expected."""

    id: str
    question: str
    category: Category
    relevant: list[str] = Field(default_factory=list)  # uids of the events
    notes: str = ""
    reference: str = ""  # the answer a well-informed human gives, in French

    @model_validator(mode="after")
    def _relevant_matches_category(self) -> "EvalQuestion":
        if (self.category == "out_of_scope") != (not self.relevant):
            raise ValueError(
                f"{self.id}: only an out_of_scope question has no relevant event"
            )
        return self


class EvalDataset(BaseModel):
    """The questions, the day they are asked on, and how far they were checked."""

    reference_date: date  # the "today" of every question
    relevant_status: Status  # of the relevant events
    reference_status: Status = "draft"  # of the reference answers
    notes: str = ""  # the rules of the annotation
    questions: list[EvalQuestion]

    @model_validator(mode="after")
    def _unique_ids(self) -> "EvalDataset":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("each question needs an id of its own")
        return self

    def unknown_uids(self, uids: set[str]) -> list[str]:
        """The relevant events missing from ``uids``, by question:
        ``question-id: uid``."""
        return [
            f"{question.id}: {uid}"
            for question in self.questions
            for uid in question.relevant
            if uid not in uids
        ]


def load_dataset(path: Path) -> EvalDataset:
    """The questions of ``path``, checked."""
    return EvalDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
