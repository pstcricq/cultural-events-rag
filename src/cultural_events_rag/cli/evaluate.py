"""The ``cultural-events-rag evaluate`` commands, their reports written into
``reports/``: ``retrieval``, the questions of the benchmark searched by each
configuration, the events found compared with those judged relevant."""

import argparse
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from elasticsearch import AuthenticationException, Elasticsearch
from elasticsearch import ConnectionError as EngineConnectionError

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
    MissingModelError,
    MissingSettingError,
    RerankerError,
)
from cultural_events_rag.evaluation.benchmark import BENCHMARK_ALIAS, rebuild_reason
from cultural_events_rag.evaluation.dataset import load_dataset
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
from cultural_events_rag.mistral import EMBEDDING_MODEL, make_embeddings
from cultural_events_rag.paths import (
    BENCHMARK_EVENTS,
    BENCHMARK_QUESTIONS,
    REPORTS_DIR,
)
from cultural_events_rag.retrieval.rerank import RERANK_MODEL
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import Settings, get_settings


def _benchmark(settings: Settings) -> tuple[Elasticsearch, str | None]:
    """A client of Elasticsearch, and why the index of the benchmark cannot be
    used: None when it can."""
    client = make_elastic_client(settings)
    events = load_events(BENCHMARK_EVENTS)
    reason = rebuild_reason(client, events, settings, BENCHMARK_ALIAS)
    if reason is None:
        return client, None
    return client, f"index {BENCHMARK_ALIAS} {reason}: run make benchmark"


def _failure(exc: Exception, url: str | None) -> str:
    """What a command says when a service fails."""
    if isinstance(exc, EngineConnectionError):
        return f"no Elasticsearch at {url}: run make docker-up"
    if isinstance(exc, AuthenticationException):
        return f"{url} refused the password: check ELASTIC_PASSWORD"
    if isinstance(exc, httpx.HTTPError):
        return f"calling Mistral: {describe(exc)}"
    return str(exc)


# A question reranked on this machine, its 20 candidates read by the
# cross-encoder: about a second.
RERANK_SECONDS = 1.0


def _go(estimate: str, yes: bool) -> bool:
    """Whether to run, its duration shown first: asked unless ``yes``."""
    print(f"Estimated time: about {estimate}.")
    return yes or confirm("Run it?")


FAILURES = (
    MissingSettingError,
    MissingModelError,
    RerankerError,
    EngineConnectionError,
    AuthenticationException,
    httpx.HTTPError,
)


def _context(settings: Settings, questions: int, asked_on: date) -> list[str]:
    """The lines that head a report: the run, the benchmark and the index."""
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
    """The report ``name`` written into reports/, as Markdown and JSON."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    page, details = REPORTS_DIR / f"{name}.md", REPORTS_DIR / f"{name}.json"
    page.write_text(markdown, encoding="utf-8")
    details.write_text(data, encoding="utf-8")
    return page, details


def _reranker_model(settings: Settings, no_rerank: bool) -> str | None:
    """The reranker of the evaluation: none when asked so or when this machine
    cannot run it (RERANK_AVAILABLE)."""
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


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag evaluate`` to the cultural-events-rag command."""
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
