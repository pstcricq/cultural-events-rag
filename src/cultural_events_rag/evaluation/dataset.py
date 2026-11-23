"""The annotated questions of the benchmark: for each question, the relevant
events and a reference answer, judged as of a reference date."""

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
    """A question, the events relevant to it, and the expected answer."""

    id: str
    question: str
    category: Category
    relevant: list[str] = Field(default_factory=list)  # uids of the events
    notes: str = ""
    reference: str = ""  # in French

    @model_validator(mode="after")
    def _relevant_matches_category(self) -> "EvalQuestion":
        if (self.category == "out_of_scope") != (not self.relevant):
            raise ValueError(
                f"{self.id}: only an out_of_scope question has no relevant event"
            )
        return self


class EvalDataset(BaseModel):
    """The questions, their reference date, and the review status of the annotations."""

    reference_date: date  # the "today" of every question
    relevant_status: Status  # of the relevant events
    reference_status: Status = "draft"  # of the reference answers
    notes: str = ""  # the annotation rules
    questions: list[EvalQuestion]

    @model_validator(mode="after")
    def _unique_ids(self) -> "EvalDataset":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("each question needs an id of its own")
        return self

    def unknown_uids(self, uids: set[str]) -> list[str]:
        """Return the relevant events missing from ``uids``, as ``question-id: uid``."""
        return [
            f"{question.id}: {uid}"
            for question in self.questions
            for uid in question.relevant
            if uid not in uids
        ]


def load_dataset(path: Path) -> EvalDataset:
    """Load and check the questions of ``path``."""
    return EvalDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
