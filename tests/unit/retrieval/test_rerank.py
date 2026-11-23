"""The reranking before any model: the candidates sorted again by the scores
of a reranker; the cross-encoder, its library replaced by a fake one, given
each pair (question, chunk) within 512 tokens, a missing one refused clearly;
its files downloaded."""

import sys
import types
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.documents import Document

from cultural_events_rag.errors import MissingModelError, RerankerError
from cultural_events_rag.retrieval.rerank import (
    CrossEncoderReranker,
    download_cross_encoder,
    rerank,
)
from cultural_events_rag.retrieval.search import EventMatch


def match(uid: str, text: str) -> EventMatch:
    return EventMatch(
        uid=uid,
        score=0.0,
        chunk=Document(id=f"{uid}-0", page_content=text),
        ranks={"hybrid": int(uid)},
    )


class WordCount:
    """Scores a text by the times it holds the words of the question."""

    def scores(self, question: str, texts: Sequence[str]) -> list[float]:
        words = question.split()
        return [
            float(sum(text.split().count(word) for word in words)) for text in texts
        ]


def test_the_candidates_are_sorted_again_and_cut_to_k() -> None:
    candidates = [
        match("1", "visite"),
        match("2", "atelier enfants"),
        match("3", "atelier"),
    ]

    kept = rerank(WordCount(), "atelier enfants", candidates, k=2)

    assert [m.uid for m in kept] == ["2", "3"]
    assert [m.score for m in kept] == [2.0, 1.0]
    assert kept[0].ranks == {"hybrid": 2}  # its rank before the reranking


def test_the_cross_encoder_reads_each_pair_within_512_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeCrossEncoder:
        def __init__(self, model: str, max_length: int) -> None:
            calls["init"] = (model, max_length)

        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            calls["pairs"] = pairs
            return [0.5] * len(pairs)

    fake = types.ModuleType("sentence_transformers")
    fake.CrossEncoder = FakeCrossEncoder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    reranker = CrossEncoderReranker("BAAI/bge-reranker-v2-m3")

    assert reranker.scores("un concert", ["a", "b"]) == [0.5, 0.5]
    assert calls["init"] == ("BAAI/bge-reranker-v2-m3", 512)
    assert calls["pairs"] == [("un concert", "a"), ("un concert", "b")]


def test_a_missing_model_says_how_to_get_it(monkeypatch: pytest.MonkeyPatch) -> None:
    class Offline:
        def __init__(self, model: str, max_length: int) -> None:
            raise OSError("not in the cache, and offline")

    fake = types.ModuleType("sentence_transformers")
    fake.CrossEncoder = Offline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    with pytest.raises(
        MissingModelError, match="BAAI/bge-reranker-v2-m3 .*make models"
    ):
        CrossEncoderReranker("BAAI/bge-reranker-v2-m3")


def test_only_the_files_a_cross_encoder_needs_are_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, list[str]]] = []

    def download(model: str, allow_patterns: list[str]) -> str:
        asked.append((model, allow_patterns))
        return "/cache/model"

    monkeypatch.setattr(
        "cultural_events_rag.retrieval.rerank.snapshot_download", download
    )

    assert download_cross_encoder("BAAI/bge-reranker-v2-m3") == "/cache/model"
    [(model, patterns)] = asked
    assert model == "BAAI/bge-reranker-v2-m3"
    assert "*.safetensors" in patterns and "*.bin" not in patterns


def test_the_cross_encoder_needs_the_rerank_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # not installed

    with pytest.raises(RerankerError, match="rerank extra"):
        CrossEncoderReranker("a/cross-encoder")
