"""The ``benchmark`` command: the annotated questions checked against the
frozen events, and the benchmark index built when missing or outdated."""

import argparse
import sys
import time
from collections import Counter

import httpx
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError
from pydantic import ValidationError

from cultural_events_rag.cli.index import Progress
from cultural_events_rag.cli.output import quiet_logs, shown
from cultural_events_rag.collection.files import load_events
from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.errors import (
    IncompleteIndexError,
    MissingModelError,
    MissingSettingError,
)
from cultural_events_rag.evaluation.benchmark import (
    BENCHMARK_ALIAS,
    build_benchmark_index,
    rebuild_reason,
)
from cultural_events_rag.evaluation.dataset import load_dataset
from cultural_events_rag.mistral import make_embeddings
from cultural_events_rag.paths import BENCHMARK_EVENTS, BENCHMARK_QUESTIONS
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import get_settings


def _benchmark(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    try:
        dataset = load_dataset(BENCHMARK_QUESTIONS)
    except ValidationError as exc:
        print(f"FAIL {shown(BENCHMARK_QUESTIONS)}: {exc}", file=sys.stderr)
        return 1
    events = load_events(BENCHMARK_EVENTS)
    unknown = dataset.unknown_uids({event.uid for event in events})
    if unknown:
        listed = ", ".join(unknown[:10])
        print(
            f"FAIL {len(unknown)} relevant events not in {shown(BENCHMARK_EVENTS)}: "
            f"{listed}",
            file=sys.stderr,
        )
        return 1

    categories = Counter(question.category for question in dataset.questions)
    relevant = sum(len(question.relevant) for question in dataset.questions)
    print(
        f"Questions: {len(dataset.questions)} <- {shown(BENCHMARK_QUESTIONS)}, "
        f"asked on {dataset.reference_date} (relevant events {dataset.relevant_status}, "
        f"answers {dataset.reference_status})"
    )
    print(f"  {', '.join(f'{name} {n}' for name, n in categories.most_common())}")
    print(f"  {relevant} relevant events in all")
    print(f"Events: {len(events)} <- {shown(BENCHMARK_EVENTS)}\n")

    url, alias = settings.elasticsearch_url, BENCHMARK_ALIAS
    try:
        client = make_elastic_client(settings)
        reason = rebuild_reason(client, events, settings, alias)
        if reason is None:
            print(f"Index: {alias} up to date")
            return 0
        print(f"Index: {alias} {reason}, building it")
        embeddings = make_embeddings(settings)
        start = time.perf_counter()
        report = build_benchmark_index(
            client, events, embeddings, settings, alias, Progress()
        )
    except (MissingSettingError, MissingModelError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    except EngineConnectionError:
        print(f"FAIL no Elasticsearch at {url}: run make docker-up", file=sys.stderr)
        return 1
    except AuthenticationException:
        print(
            f"FAIL {url} refused the password: check ELASTIC_PASSWORD", file=sys.stderr
        )
        return 1
    except httpx.HTTPError as exc:
        print(f"FAIL embedding: {describe(exc)}, index unchanged", file=sys.stderr)
        return 1
    except IncompleteIndexError as exc:
        print(f"FAIL {exc}: index unchanged", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - start
    print(f"\nIndex: {alias} -> {report.index}, {report.documents} documents")
    print(f"Built in {elapsed:.1f} s")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the ``benchmark`` command to the parser of ``cultural-events-rag``."""
    benchmark = commands.add_parser(
        "benchmark", help="check the benchmark and build its index when needed"
    )
    benchmark.set_defaults(run=_benchmark)
