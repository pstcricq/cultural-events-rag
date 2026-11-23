"""The index of the benchmark against a real Elasticsearch, with a fake
embedding model: built under its own alias when missing, then up to date, and
rebuilt when built with other settings or on other events; the command end to
end."""

from pathlib import Path

import pytest
from elasticsearch import Elasticsearch
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.cli import main
from cultural_events_rag.collection.files import save_events
from cultural_events_rag.elastic import index_alias
from cultural_events_rag.evaluation.benchmark import (
    build_benchmark_index,
    rebuild_reason,
)
from cultural_events_rag.indexing.store import served_indices
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)


@pytest.fixture
def alias(settings: Settings) -> str:
    return f"{settings.elasticsearch_index}-benchmark"


def test_the_benchmark_index_is_built_then_up_to_date(
    client: Elasticsearch, settings: Settings, event: Event, alias: str
) -> None:
    assert rebuild_reason(client, [event], settings, alias) == "missing"

    report = build_benchmark_index(client, [event], FAKE, settings, alias)

    assert served_indices(client, alias) == [report.index]
    assert served_indices(client, index_alias(settings)) == []  # not the app's
    assert rebuild_reason(client, [event], settings, alias) is None


def test_an_index_built_otherwise_or_other_events_rebuild_it(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    alias: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_benchmark_index(client, [event], FAKE, settings, alias)
    other = event.model_copy(update={"uid": "2"})

    with monkeypatch.context() as changed:
        changed.setattr("cultural_events_rag.indexing.build.CHUNK_SIZE", 500)
        assert rebuild_reason(client, [event], settings, alias) == (
            "outdated (chunk_size: 1000 instead of 500)"
        )
    assert rebuild_reason(client, [event, other], settings, alias) == (
        "built on other events"
    )


def test_benchmark_builds_the_index_once(
    tmp_path: Path,
    settings: Settings,
    event: Event,
    alias: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    questions, events = tmp_path / "questions.json", tmp_path / "events.jsonl"
    questions.write_text(
        '{"reference_date": "2026-10-19", "relevant_status": "validated", "questions": '
        f'[{{"id": "q1", "question": "Une visite ?", "category": "theme", '
        f'"relevant": ["{event.uid}"]}}]}}',
        encoding="utf-8",
    )
    save_events([event], events)
    prefix = "cultural_events_rag.cli.benchmark"
    monkeypatch.setattr(f"{prefix}.BENCHMARK_QUESTIONS", questions)
    monkeypatch.setattr(f"{prefix}.BENCHMARK_EVENTS", events)
    monkeypatch.setattr(f"{prefix}.BENCHMARK_ALIAS", alias)
    monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)
    monkeypatch.setattr(f"{prefix}.make_embeddings", lambda _: FAKE)

    assert main(["benchmark"]) == 0
    out = capsys.readouterr().out
    assert f"Index: {alias} missing, building it" in out
    assert f"Index: {alias} -> {alias}-" in out

    assert main(["benchmark"]) == 0
    assert f"Index: {alias} up to date" in capsys.readouterr().out
