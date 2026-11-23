"""Tests of the ``benchmark`` command without Elasticsearch: invalid questions
and missing relevant events refused, the summary, an up-to-date index kept."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings


def _benchmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    events: list[Event],
    questions: list[dict[str, Any]],
) -> None:
    questions_file, events_file = tmp_path / "questions.json", tmp_path / "events.jsonl"
    questions_file.write_text(
        json.dumps(
            {
                "reference_date": "2026-10-19",
                "relevant_status": "validated",
                "questions": questions,
            }
        ),
        encoding="utf-8",
    )
    save_events(events, events_file)
    prefix = "cultural_events_rag.cli.benchmark"
    monkeypatch.setattr(f"{prefix}.BENCHMARK_QUESTIONS", questions_file)
    monkeypatch.setattr(f"{prefix}.BENCHMARK_EVENTS", events_file)
    settings = Settings(
        _env_file=None,
        elasticsearch_url="http://127.0.0.1:9200",
        elastic_user="elastic",
        elastic_password=SecretStr("password"),
    )
    monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)


def test_benchmark_refuses_invalid_questions(
    tmp_path: Path,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    questions = [{"id": "q1", "question": "Un concert ?", "category": "theme"}]
    _benchmark(tmp_path, monkeypatch, [event], questions)

    assert main(["benchmark"]) == 1

    assert (
        "only an out_of_scope question has no relevant event" in capsys.readouterr().err
    )


def test_benchmark_refuses_a_relevant_event_missing(
    tmp_path: Path,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    questions = [
        {"id": "q1", "question": "Une visite ?", "category": "theme", "relevant": ["9"]}
    ]
    _benchmark(tmp_path, monkeypatch, [event], questions)

    assert main(["benchmark"]) == 1

    assert "FAIL 1 relevant events not in " in (err := capsys.readouterr().err)
    assert "q1: 9" in err


def test_benchmark_leaves_an_index_up_to_date(
    tmp_path: Path,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    questions: list[dict[str, Any]] = [
        {
            "id": "q1",
            "question": "Une visite ?",
            "category": "theme",
            "relevant": [event.uid],
        },
        {"id": "q2", "question": "Un match de foot ?", "category": "out_of_scope"},
    ]
    _benchmark(tmp_path, monkeypatch, [event], questions)
    monkeypatch.setattr(
        "cultural_events_rag.cli.benchmark.rebuild_reason", lambda *_args: None
    )

    assert main(["benchmark"]) == 0

    out = capsys.readouterr().out
    assert "Questions: 2 <- " in out
    assert "asked on 2026-10-19 (relevant events validated, answers draft)" in out
    assert "  theme 1, out_of_scope 1\n  1 relevant events in all" in out
    assert "Events: 1 <- " in out
    assert "Index: events-benchmark up to date" in out
