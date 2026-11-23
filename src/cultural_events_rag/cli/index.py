"""The ``index`` command: the documents of the events embedded and written into
a new Elasticsearch index, then the alias moved onto it."""

import argparse
import sys
import time

import httpx
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.cli.output import quiet_logs, shown
from cultural_events_rag.collection.files import load_events
from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.errors import (
    IncompleteIndexError,
    MissingModelError,
    MissingSettingError,
)
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.indexing.chunking import CHUNK_OVERLAP, CHUNK_SIZE
from cultural_events_rag.mistral import EMBEDDING_MODEL, make_embeddings
from cultural_events_rag.paths import EVENTS_FILE
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import get_settings


class Progress:
    """Progress printed at each tenth of the documents embedded, one line each."""

    def __init__(self) -> None:
        self.step = 0

    def __call__(self, done: int, total: int) -> None:
        step = done * 10 // total
        if step > self.step:
            self.step = step
            print(f"Embedding: {done * 100 // total:3d}% ({done}/{total} documents)")


def _index(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    if not EVENTS_FILE.is_file():
        print(
            f"FAIL no events in {shown(EVENTS_FILE)}: run make process", file=sys.stderr
        )
        return 1
    url = settings.elasticsearch_url
    try:
        client = make_elastic_client(settings)
        embeddings = make_embeddings(settings)
        events = load_events(EVENTS_FILE)
        print(
            f"Events: {len(events)} <- {shown(EVENTS_FILE)}, "
            f"model: {EMBEDDING_MODEL}, "
            f"chunks: {CHUNK_SIZE} chars, {CHUNK_OVERLAP} overlap\n"
        )
        start = time.perf_counter()
        report = build_index(client, events, embeddings, settings, Progress())
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

    print(f"\nDocuments: {report.documents}, in {elapsed:.1f} s")
    print(f"Index: {settings.elasticsearch_index} -> {report.index}")
    if report.replaced:
        print(f"Replaced: {', '.join(report.replaced)}")
    if report.left:
        print(
            f"WARN old indices not deleted: {', '.join(report.left)} "
            "(delete them in Kibana, Index Management)",
            file=sys.stderr,
        )
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the ``index`` command to the parser of ``cultural-events-rag``."""
    index = commands.add_parser(
        "index", help="embed the documents of the events and write their index"
    )
    index.set_defaults(run=_index)
