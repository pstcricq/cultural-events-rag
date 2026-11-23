"""Tests of the evaluation of the search against a real Elasticsearch, with a
fake embedding model, and the command with its report."""

from datetime import date
from pathlib import Path

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.evaluation.benchmark import build_benchmark_index
from cultural_events_rag.evaluation.dataset import EvalDataset, EvalQuestion
from cultural_events_rag.evaluation.retrieval import RetrievalConfig, evaluate
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)


def _dataset(event: Event) -> EvalDataset:
    return EvalDataset(
        reference_date=date(2026, 6, 1),
        relevant_status="validated",
        questions=[
            EvalQuestion(
                id="q1",
                question="Une visite guidée",
                category="theme",
                relevant=[event.uid],
            ),
            EvalQuestion(
                id="q2", question="Un match de rugby", category="out_of_scope"
            ),
        ],
    )


@pytest.fixture
def alias(client: Elasticsearch, settings: Settings, event: Event) -> str:
    alias = f"{settings.elasticsearch_index}-benchmark"
    build_benchmark_index(client, [event], FAKE, settings, alias)
    return alias


def test_each_question_is_searched_as_of_the_reference_date(
    client: Elasticsearch, event: Event, alias: str
) -> None:
    results = evaluate(
        client, alias, _dataset(event), RetrievalConfig("hybrid", False), FAKE, None
    )

    # The vector search always ranks the nearest: out of scope too.
    assert [r.ranked for r in results] == [[event.uid], [event.uid]]
    assert results[0].filters == "-"  # the default period alone
    assert results[0].first_relevant_rank == 1


def test_evaluate_retrieval_writes_its_report(
    tmp_path: Path,
    settings: Settings,
    event: Event,
    alias: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
        "make_embeddings": lambda _: FAKE,
    }.items():
        monkeypatch.setattr(f"{prefix}.{name}", value)

    assert main(["evaluate", "retrieval", "--no-rerank", "--yes"]) == 0

    out = capsys.readouterr().out
    assert "Questions: 2, asked on 2026-06-01, in " in out
    # Aligned in columns, its words apart.
    assert "hybrid 1.00 1.00 0.20 1.00 1.00" in " ".join(out.split())
    assert (tmp_path / "reports" / "retrieval.md").is_file()
    assert (tmp_path / "reports" / "retrieval.json").is_file()


def test_evaluate_retrieval_needs_the_benchmark_index(
    settings: Settings,
    event: Event,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    questions, events = tmp_path / "questions.json", tmp_path / "events.jsonl"
    questions.write_text(_dataset(event).model_dump_json(), encoding="utf-8")
    save_events([event], events)
    prefix = "cultural_events_rag.cli.evaluate"
    monkeypatch.setattr(f"{prefix}.BENCHMARK_QUESTIONS", questions)
    monkeypatch.setattr(f"{prefix}.BENCHMARK_EVENTS", events)
    monkeypatch.setattr(f"{prefix}.BENCHMARK_ALIAS", "no-such-alias")
    monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)

    assert main(["evaluate", "retrieval", "--no-rerank", "--yes"]) == 1

    assert (
        "FAIL index no-such-alias missing: run make benchmark"
        in capsys.readouterr().err
    )
