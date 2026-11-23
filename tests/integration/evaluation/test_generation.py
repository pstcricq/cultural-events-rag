"""The evaluation of the answers end to end against a real Elasticsearch, with
a fake embedding model and a fake LLM: each question searched and answered as
of its reference date, the report written."""

import re
from pathlib import Path
from typing import Any

import pytest
from elasticsearch import Elasticsearch
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import RunnableLambda

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.evaluation.benchmark import build_benchmark_index
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings
from tests.integration.evaluation.test_retrieval import FAKE, _dataset


def _answer(prompt: PromptValue) -> dict[str, Any]:
    """Every event given recommended, none for rugby."""
    text = prompt.to_string()
    if "rugby" in text.rsplit("Human:", 1)[-1]:
        return {"answer": "Aucun événement ne correspond.", "event_uids": []}
    return {"answer": "Voici.", "event_uids": re.findall(r'<event uid="(\w+)">', text)}


@pytest.fixture
def benchmark(
    tmp_path: Path,
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """The benchmark of one event and two questions, its index built; the
    reports directory."""
    alias = f"{settings.elasticsearch_index}-benchmark"
    build_benchmark_index(client, [event], FAKE, settings, alias)
    questions, events = tmp_path / "questions.json", tmp_path / "events.jsonl"
    questions.write_text(_dataset(event).model_dump_json(), encoding="utf-8")
    save_events([event], events)
    prefix = "cultural_events_rag.cli.evaluate"
    for name, value in {
        "BENCHMARK_QUESTIONS": questions,
        "BENCHMARK_EVENTS": events,
        "BENCHMARK_ALIAS": alias,
        "REPORTS_DIR": tmp_path / "reports",
        "get_settings": lambda: settings,
    }.items():
        monkeypatch.setattr(f"{prefix}.{name}", value)
    for name, value in {
        "make_embeddings": lambda _: FAKE,
        "make_chat_model": lambda *_: None,
        "recommender": lambda _: RunnableLambda(_answer),
    }.items():
        monkeypatch.setattr(f"cultural_events_rag.assistant.{name}", value)
    return tmp_path / "reports"


def test_evaluate_generation_writes_its_report(
    benchmark: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["evaluate", "generation", "--no-judge", "--yes"]) == 0

    out = capsys.readouterr().out
    assert "Questions: 2, asked on 2026-06-01, in " in out
    printed = " ".join(out.split())  # aligned in columns
    assert "Estimated time: about 1 min: the answers 1 min, at 2 calls a minute." in out
    assert "Recommendation precision 1.00 1" in printed
    assert "Abstention (out of scope) 1.00 1" in printed
    report = (benchmark / "generation.md").read_text(encoding="utf-8")
    assert "| Un match de rugby | 0 | Aucun événement ne correspond. |" in report
    assert '"q1": {\n    "answer": "Voici."' in (
        benchmark / "generation.json"
    ).read_text(encoding="utf-8")


def test_evaluate_generation_needs_the_benchmark_index(
    benchmark: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("cultural_events_rag.cli.evaluate.BENCHMARK_ALIAS", "no-alias")

    assert main(["evaluate", "generation", "--no-judge", "--yes"]) == 1

    assert "FAIL index no-alias missing: run make benchmark" in capsys.readouterr().err


class Judge:
    """Rates every answer faithful."""

    async def score(self, *args: Any) -> dict[str, float]:
        return {"faithfulness": 1.0}


def test_evaluate_generation_with_the_judge(
    benchmark: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("cultural_events_rag.cli.evaluate._judge", lambda *_: Judge())

    assert main(["evaluate", "generation", "--yes"]) == 0

    out = capsys.readouterr().out
    assert "Faithfulness 1.00 1" in " ".join(out.split())
    assert "Judged in " in out
    report = (benchmark / "generation.md").read_text(encoding="utf-8")
    assert "- Judge: " in report
