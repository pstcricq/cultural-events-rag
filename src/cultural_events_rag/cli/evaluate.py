"""The ``evaluate`` commands, their reports written into ``reports/``:
``retrieval`` compares the search configurations on the benchmark;
``generation`` evaluates the answers of the assistant."""

import argparse
import asyncio
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from elasticsearch import AuthenticationException, Elasticsearch
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.assistant import SEARCH_MODE, load_assistant, reranker_model
from cultural_events_rag.cli.output import (
    aligned,
    confirm,
    duration,
    quiet_logs,
    shown,
)
from cultural_events_rag.cli.search import load_reranker
from cultural_events_rag.collection.files import load_events
from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.errors import (
    GenerationError,
    JudgeError,
    MissingModelError,
    MissingSettingError,
    RerankerError,
)
from cultural_events_rag.evaluation.benchmark import BENCHMARK_ALIAS, rebuild_reason
from cultural_events_rag.evaluation.dataset import load_dataset
from cultural_events_rag.evaluation.generation import (
    JUDGE_CALLS,
    evaluate_answers,
    judge_answers,
)
from cultural_events_rag.evaluation.generation_report import (
    render as render_answers,
)
from cultural_events_rag.evaluation.generation_report import scores
from cultural_events_rag.evaluation.generation_report import (
    to_json as answers_json,
)
from cultural_events_rag.evaluation.retrieval import (
    CANDIDATES,
    CONFIGS,
    CachedEmbeddings,
    QuestionResult,
    RetrievalConfig,
    evaluate,
)
from cultural_events_rag.evaluation.retrieval_report import (
    configurations,
    render,
    to_json,
)
from cultural_events_rag.indexing.chunking import CHUNK_OVERLAP, CHUNK_SIZE
from cultural_events_rag.mistral import (
    EMBEDDING_MODEL,
    JUDGE_MODEL,
    LLM_MODEL,
    Pacer,
    make_embeddings,
    requests_per_minute,
)
from cultural_events_rag.paths import (
    BENCHMARK_EVENTS,
    BENCHMARK_QUESTIONS,
    REPORTS_DIR,
)
from cultural_events_rag.retrieval.rerank import RERANK_MODEL
from cultural_events_rag.retrieval.search import SEARCH_K
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import Settings, get_settings

if TYPE_CHECKING:  # the eval extra, only to judge
    from cultural_events_rag.evaluation.judge import RagasJudge


def _benchmark(settings: Settings) -> tuple[Elasticsearch, str | None]:
    """Return an Elasticsearch client and why the benchmark index cannot be
    used, or None."""
    client = make_elastic_client(settings)
    events = load_events(BENCHMARK_EVENTS)
    reason = rebuild_reason(client, events, settings, BENCHMARK_ALIAS)
    if reason is None:
        return client, None
    return client, f"index {BENCHMARK_ALIAS} {reason}: run make benchmark"


def _failure(exc: Exception, url: str | None) -> str:
    """Return the message of a command when a service fails."""
    if isinstance(exc, EngineConnectionError):
        return f"no Elasticsearch at {url}: run make docker-up"
    if isinstance(exc, AuthenticationException):
        return f"{url} refused the password: check ELASTIC_PASSWORD"
    if isinstance(exc, httpx.HTTPError):
        return f"calling Mistral: {describe(exc)}"
    return str(exc)


# The time to rerank one question on this machine, in seconds.
RERANK_SECONDS = 1.0


def _go(estimate: str, yes: bool) -> bool:
    """Return whether to run, after showing the estimated duration; asked
    unless ``yes``."""
    print(f"Estimated time: about {estimate}.")
    return yes or confirm("Run it?")


FAILURES = (
    JudgeError,
    MissingSettingError,
    MissingModelError,
    RerankerError,
    GenerationError,
    EngineConnectionError,
    AuthenticationException,
    httpx.HTTPError,
)


def _judge(settings: Settings, pacer: Pacer) -> "RagasJudge":
    """Return the Ragas judge, its calls spaced by ``pacer``."""
    try:
        from cultural_events_rag.evaluation.judge import RagasJudge
    except ImportError as exc:
        raise JudgeError("the judge needs the eval extra: run make install") from exc
    return RagasJudge(settings, pacer)


def _context(settings: Settings, questions: int, asked_on: date) -> list[str]:
    """Return the header lines of a report: the run, the benchmark and the index."""
    events = len(load_events(BENCHMARK_EVENTS))
    return [
        f"Run: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        (
            f"Questions: `{shown(BENCHMARK_QUESTIONS)}`, {questions}, "
            f"asked on {asked_on}"
        ),
        f"Events: `{shown(BENCHMARK_EVENTS)}`, {events}, index `{BENCHMARK_ALIAS}`",
        (
            f"Index: {EMBEDDING_MODEL}, chunks of {CHUNK_SIZE} "
            f"characters, {CHUNK_OVERLAP} of overlap"
        ),
    ]


def _write(name: str, markdown: str, data: str) -> tuple[Path, Path]:
    """Write the report ``name`` into ``reports/``, as Markdown and JSON."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    page, details = REPORTS_DIR / f"{name}.md", REPORTS_DIR / f"{name}.json"
    page.write_text(markdown, encoding="utf-8")
    details.write_text(data, encoding="utf-8")
    return page, details


def _reranker_model(settings: Settings, no_rerank: bool) -> str | None:
    """Return the reranker of the evaluation: none when not asked for, or when
    the machine cannot run it (``RERANK_AVAILABLE``)."""
    if no_rerank:
        return None
    if settings.rerank_available is None:
        raise MissingSettingError("RERANK_AVAILABLE is not set: add it to .env")
    return RERANK_MODEL if settings.rerank_available else None


def _retrieval(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    dataset = load_dataset(BENCHMARK_QUESTIONS)
    results: dict[RetrievalConfig, list[QuestionResult]] = {}
    try:
        model = _reranker_model(settings, args.no_rerank)
        configs = [config for config in CONFIGS if model or not config.rerank]
        client, problem = _benchmark(settings)
        if problem:
            print(f"FAIL {problem}", file=sys.stderr)
            return 1
        reranked = sum(1 for config in configs if config.rerank)
        seconds = 30 + len(dataset.questions) * reranked * RERANK_SECONDS
        if not _go(f"{duration(seconds)}, {len(configs)} configurations", args.yes):
            print("Nothing run")
            return 0
        embeddings = CachedEmbeddings(make_embeddings(settings))
        reranker = load_reranker(model) if model else None
        print(
            f"Questions: {len(dataset.questions)}, asked on {dataset.reference_date}, "
            f"in {BENCHMARK_ALIAS}\n"
        )
        width = max(len(config.name) for config in configs)
        for config in configs:
            start = time.perf_counter()
            results[config] = evaluate(
                client, BENCHMARK_ALIAS, dataset, config, embeddings, reranker
            )
            elapsed = time.perf_counter() - start
            print(f"{config.name.ljust(width)}  {elapsed:5.1f} s", flush=True)
    except FAILURES as exc:
        print(f"FAIL {_failure(exc, settings.elasticsearch_url)}", file=sys.stderr)
        return 1

    context = _context(settings, len(dataset.questions), dataset.reference_date)
    context += [
        f"Reranker: {model} on the first {CANDIDATES} events"
        if model
        else "Reranker: none",
    ]
    page, rankings = _write(
        "retrieval", render(dataset, results, context), to_json(results)
    )
    print()
    for line in aligned(configurations(results), bold=sys.stdout.isatty()):
        print(line)
    print(f"\nReport: {shown(page)}, rankings: {shown(rankings)}")
    return 0


def _generation(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    dataset = load_dataset(BENCHMARK_QUESTIONS)
    try:
        config = RetrievalConfig(SEARCH_MODE, bool(reranker_model(settings)))
        per_minute = requests_per_minute(settings)
        client, problem = _benchmark(settings)
        if problem:
            print(f"FAIL {problem}", file=sys.stderr)
            return 1
        interval = 60 / per_minute
        answering = len(dataset.questions) * interval
        in_scope = sum(1 for question in dataset.questions if question.relevant)
        to_judge = 0.0 if args.no_judge else in_scope * JUDGE_CALLS * interval
        estimate = (
            f"{duration(answering + to_judge)}: the answers {duration(answering)}"
            + (f", the judge {duration(to_judge)}" if to_judge else "")
            + f", at {per_minute:g} calls a minute"
        )
        if not _go(estimate, args.yes):
            print("Nothing run")
            return 0
        # The chat model and the judge share the quota of the plan.
        pacer = Pacer(per_minute)
        assistant = load_assistant(
            settings,
            client,
            BENCHMARK_ALIAS,
            pacer=pacer,
            load_reranker=load_reranker,
        )
        judge = None if args.no_judge else _judge(settings, pacer)
        print(
            f"Questions: {len(dataset.questions)}, asked on {dataset.reference_date}, "
            f"in {BENCHMARK_ALIAS}, {config.name}, answered by {LLM_MODEL}"
            + (f", judged by {JUDGE_MODEL}" if judge else "")
            + "\n"
        )
        start = time.perf_counter()
        results = evaluate_answers(assistant, dataset)
        elapsed = time.perf_counter() - start
        print(f"Answered in {duration(elapsed)}")
        judging = 0.0
        if judge:
            start = time.perf_counter()
            results = asyncio.run(judge_answers(results, judge))
            judging = time.perf_counter() - start
            print(f"Judged in {duration(judging)}")
    except FAILURES as exc:
        print(f"FAIL {_failure(exc, settings.elasticsearch_url)}", file=sys.stderr)
        return 1

    context = _context(settings, len(dataset.questions), dataset.reference_date)
    context += [
        (f"Search: {config.name}, the first {SEARCH_K} events given to the LLM"),
        f"Answers: {LLM_MODEL}, in {elapsed:.0f} s",
        (
            f"Judge: {JUDGE_MODEL} (Ragas), in {judging:.0f} s"
            if judge
            else "Judge: none"
        ),
        (
            f"Calls to the chat models: {per_minute:g} a "
            "minute, the quota of the Mistral plan"
        ),
    ]
    page, answers = _write(
        "generation", render_answers(results, context), answers_json(results)
    )
    print()
    for line in aligned(scores(results), bold=sys.stdout.isatty()):
        print(line)
    print(f"\nReport: {shown(page)}, answers: {shown(answers)}")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the ``evaluate`` command to the parser of ``cultural-events-rag``."""
    evaluate_ = commands.add_parser(
        "evaluate", help="measure the assistant on the benchmark"
    )
    steps = evaluate_.add_subparsers(dest="step", required=True)
    retrieval = steps.add_parser(
        "retrieval", help="compare the configurations of the search"
    )
    retrieval.add_argument(
        "--no-rerank",
        action="store_true",
        help="only the configurations without reranker",
    )
    retrieval.add_argument(
        "--yes", action="store_true", help="run without asking, its duration shown"
    )
    retrieval.set_defaults(run=_retrieval)
    generation = steps.add_parser(
        "generation",
        help="answer the questions with the configuration kept, and measure them",
    )
    generation.add_argument(
        "--no-judge",
        action="store_true",
        help="the exact checks only, without the Ragas judge (hours on the free plan)",
    )
    generation.add_argument(
        "--yes", action="store_true", help="run without asking, its duration shown"
    )
    generation.set_defaults(run=_generation)
