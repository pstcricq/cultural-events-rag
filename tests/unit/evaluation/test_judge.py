"""Tests of the Ragas judge, its metrics replaced: the scores kept, a failed or
undefined metric left out."""

import asyncio
import math
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from cultural_events_rag.cli.evaluate import _judge
from cultural_events_rag.errors import JudgeError, MissingSettingError
from cultural_events_rag.evaluation.judge import RagasJudge
from cultural_events_rag.mistral import Pacer
from cultural_events_rag.settings import Settings

SETTINGS = Settings(_env_file=None, mistral_api_key=SecretStr("key"))


class Metric:
    """A metric of Ragas giving ``value``, or raising ``error``."""

    def __init__(self, value: float = 0.0, error: Exception | None = None) -> None:
        self.value, self.error = value, error
        self.inputs: dict[str, Any] = {}

    async def ascore(self, **inputs: Any) -> SimpleNamespace:
        self.inputs = inputs
        if self.error:
            raise self.error
        return SimpleNamespace(value=self.value)


def test_a_failed_or_undefined_metric_is_left_out() -> None:
    judge = RagasJudge(SETTINGS, Pacer(2))
    judge.faithfulness = Metric(0.9)  # type: ignore[assignment]
    judge.relevancy = Metric(error=ValueError("no JSON"))  # type: ignore[assignment]
    judge.correctness = Metric(math.nan)  # type: ignore[assignment]

    scores = asyncio.run(
        judge.score("Un concert ?", "Voici.", ["Titre : a"], "Le concert a.")
    )

    assert scores == {"faithfulness": 0.9}
    assert judge.faithfulness.inputs == {  # type: ignore[attr-defined]
        "user_input": "Un concert ?",
        "response": "Voici.",
        "retrieved_contexts": ["Titre : a"],
    }
    assert judge.correctness.inputs == {  # type: ignore[attr-defined]
        "response": "Voici.",
        "reference": "Le concert a.",
    }


def test_the_judge_needs_the_key() -> None:
    with pytest.raises(MissingSettingError, match="MISTRAL_API_KEY"):
        RagasJudge(Settings(_env_file=None), Pacer(2))


def test_the_judge_needs_the_eval_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "cultural_events_rag.evaluation.judge", None)

    with pytest.raises(JudgeError, match="run make install"):
        _judge(SETTINGS, Pacer(2))
