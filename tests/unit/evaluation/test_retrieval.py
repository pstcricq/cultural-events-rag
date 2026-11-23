"""The metrics of the search on hand-made rankings, measured where the
assistant cuts, the comparison question by question, the question vectors asked
once, and the report."""

import json
from datetime import date

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.evaluation.dataset import EvalDataset, EvalQuestion
from cultural_events_rag.evaluation.markdown import bold_best
from cultural_events_rag.evaluation.retrieval import (
    CANDIDATES,
    CONFIGS,
    SHOWN,
    CachedEmbeddings,
    QuestionResult,
    RetrievalConfig,
    added_filters,
    hit_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    summary,
    wins,
)
from cultural_events_rag.evaluation.retrieval_report import render, to_json
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import RERANK_CANDIDATES, SEARCH_K

RANKED = ["a", "x", "b", "y", "z", "c"]
RELEVANT = {"a", "b", "c"}


def test_the_metrics_are_measured_where_the_assistant_cuts() -> None:
    assert (SHOWN, CANDIDATES) == (SEARCH_K, RERANK_CANDIDATES)


def test_the_metrics_of_a_ranking() -> None:
    assert hit_at_k(RANKED, RELEVANT, 1) == 1.0
    assert hit_at_k(["x", "y"], RELEVANT, 2) == 0.0
    assert recall_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 3)
    assert precision_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 5)
    assert reciprocal_rank(["x", "y", "b"], RELEVANT) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x"], RELEVANT) == 0.0


def test_recall_is_capped_at_k_relevant_events() -> None:
    many = {f"e{n}" for n in range(200)}

    assert recall_at_k(["e1", "e2", "e3", "e4", "e5"], many, 5) == 1.0


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
    q: EvalQuestion, ranked: list[str], scores: list[float] | None = None
) -> QuestionResult:
    return QuestionResult(
        question=q,
        ranked=ranked,
        titles=[f"Event {uid}" for uid in ranked],
        scores=scores or [0.5] * len(ranked),
        filters="-",
    )


Q1, Q2 = question("q1", ["a"]), question("q2", ["b"], "time")
OUT = question("out", [], "out_of_scope")


def test_the_summary_leaves_out_the_out_of_scope_questions() -> None:
    results = [result(Q1, ["a"]), result(Q2, ["x"]), result(OUT, ["x"])]

    assert summary(results)["hit@5"] == 0.5
    assert summary(results)["mrr"] == 0.5


def test_the_questions_a_configuration_wins() -> None:
    first = [result(Q1, ["a"]), result(Q2, ["x"])]
    second = [result(Q1, ["a"]), result(Q2, ["b"])]

    assert wins(second, first) == 1
    assert wins(first, second) == 0


def test_each_question_is_embedded_once() -> None:
    asked: list[str] = []

    class Counting(DeterministicFakeEmbedding):
        def embed_query(self, text: str) -> list[float]:
            asked.append(text)
            return super().embed_query(text)

    cached = CachedEmbeddings(Counting(size=4))

    assert cached.embed_query("un concert") == cached.embed_query("un concert")
    assert asked == ["un concert"]
    assert len(cached.embed_documents(["a", "b"])) == 2


def test_the_six_configurations() -> None:
    assert [config.name for config in CONFIGS] == [
        "lexical",
        "vector",
        "hybrid",
        "lexical + rerank",
        "vector + rerank",
        "hybrid + rerank",
    ]


def test_the_report() -> None:
    dataset = EvalDataset(
        reference_date=date(2026, 10, 19),
        relevant_status="validated",
        questions=[Q1, Q2, OUT],
    )
    lexical, hybrid = RetrievalConfig("lexical", False), RetrievalConfig("hybrid", True)
    results = {
        lexical: [result(Q1, ["a"]), result(Q2, ["x"]), result(OUT, ["x"])],
        hybrid: [
            result(Q1, ["a"], [0.9]),
            result(Q2, ["b"], [0.7]),
            result(OUT, ["y"], [0.8]),
        ],
    }

    report = render(dataset, results, ["Run: now"])

    assert "- Run: now" in report
    assert (
        "| MRR | $\\dfrac{1}{r}$ | $r$ is the rank of the first relevant event"
        in report
    )
    assert "| Metric | For a question | What it says |\n|:---:|:---:|---|" in report
    assert "A row where every configuration scores the same has none" in report
    assert "## Configurations (2 questions with relevant events)" in report
    assert "| lexical | 0.50 | 0.50 | 0.10 | 0.50 | 0.50 |" in report
    assert (
        "| hybrid + rerank | **1.00** | **1.00** | **0.20** | **1.00** | **1.00** |"
        in report
    )
    assert "| Better than → | lexical | hybrid + rerank |" in report
    assert "| hybrid + rerank | 1 | - |" in report
    assert "| theme (1) | 1.00 | 1.00 |" in report  # alike: none in bold
    assert "| time (1) | 0.00 | **1.00** |" in report
    assert "besides the events from 2026-10-19 on that every search keeps" in report
    assert "| Question q2 ? | time | 1 | - | 0.00 | **1.00** |" in report
    assert "## Out-of-scope questions (1): the first event found" in report
    assert "| Question out ? | Event x | Event y |" in report
    assert "| hybrid + rerank | 0.800 | 0.700 | 0.800 | 0.800 | 1 / 2 |" in report
    assert '\n    "q2": ["b"]' in to_json(results)
    assert json.loads(to_json(results)) == {
        "lexical": {"q1": ["a"], "q2": ["x"], "out": ["x"]},
        "hybrid + rerank": {"q1": ["a"], "q2": ["b"], "out": ["y"]},
    }


def test_two_scores_shown_alike_are_both_in_bold() -> None:
    assert bold_best([0.896, 0.904, 0.5]) == ["**0.90**", "**0.90**", "0.50"]
    assert bold_best([0.896, 0.904]) == ["0.90", "0.90"]


def test_the_filters_added_to_the_default_period() -> None:
    today = date(2026, 10, 19)

    assert added_filters(SearchFilters(date_from=today), today) == "-"
    assert added_filters(SearchFilters(date_from=today, free=True), today) == "free"
    assert (
        added_filters(SearchFilters(date_from=today, date_to=today), today)
        == "dates: 2026-10-19 to 2026-10-19"
    )


def test_a_long_title_is_cut() -> None:
    long = QuestionResult(
        question=OUT, ranked=["x"], titles=["T" * 60], scores=[0.1], filters="none"
    )
    dataset = EvalDataset(
        reference_date=date(2026, 10, 19),
        relevant_status="validated",
        questions=[Q1, OUT],
    )
    results = {RetrievalConfig("lexical", False): [result(Q1, ["a"]), long]}

    assert "T" * 39 + "…" in render(dataset, results, [])
