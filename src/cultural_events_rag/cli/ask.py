"""The ``cultural-events-rag ask`` command: the answer of the assistant to a
question, written by the LLM from the events of the index served, and the
events it recommends."""

import argparse
import sys
import textwrap
import time
from datetime import date, datetime

import httpx
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.assistant import load_assistant
from cultural_events_rag.cli.output import question, quiet_logs
from cultural_events_rag.cli.search import load_reranker, where_and_when
from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.errors import (
    GenerationError,
    MissingModelError,
    MissingSettingError,
    RerankerError,
)
from cultural_events_rag.generation.answer import Answer
from cultural_events_rag.mistral import LLM_MODEL
from cultural_events_rag.retrieval.search import index_problem
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import get_settings

WIDTH = 88


def _show(answer: Answer) -> None:
    """The answer, then each event it recommends: its title, its place, slot
    and price, and its link."""
    filters = answer.retrieval.filters
    for paragraph in answer.text.splitlines():
        print(textwrap.fill(paragraph, WIDTH) if paragraph else "")
    found = len(answer.retrieval.matches)
    print(f"\nEvents recommended: {len(answer.events)} of the {found} found\n")
    for rank, match in enumerate(answer.events, 1):
        metadata = match.chunk.metadata
        print(f"{rank:>2}. {metadata['title']}")
        print(f"    {where_and_when(match, filters)}")
        if metadata["url"]:
            print(f"    {metadata['url']}")
        print()


def _ask(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    url = settings.elasticsearch_url
    today: date = args.today or datetime.now(TIMEZONE).date()
    try:
        client = make_elastic_client(settings)
        problem = index_problem(client, settings)
        if problem:
            print(f"FAIL {problem}", file=sys.stderr)
            return 1
        assistant = load_assistant(
            settings, client, rerank=not args.no_rerank, load_reranker=load_reranker
        )
        start = time.perf_counter()
        retrieval = assistant.search(args.question, today)
        searched = time.perf_counter() - start
    except (RerankerError, MissingModelError, MissingSettingError) as exc:
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
        print(f"FAIL embedding the question: {describe(exc)}", file=sys.stderr)
        return 1

    start = time.perf_counter()
    try:
        answer = assistant.answer(args.question, today, retrieval)
    except httpx.HTTPError as exc:
        print(f"FAIL generating the answer: {describe(exc)}", file=sys.stderr)
        return 1
    except GenerationError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    generated = time.perf_counter() - start

    print(f"Question: {args.question}")
    print(
        f"Asked on {today}, {len(retrieval.matches)} events found in {searched:.1f} s, "
        f"answer by {LLM_MODEL} in {generated:.1f} s"
    )
    print(f"Filters: {retrieval.filters.describe()}\n")
    _show(answer)
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag ask`` to the cultural-events-rag command."""
    ask = commands.add_parser("ask", help="the answer of the assistant to a question")
    ask.add_argument("question", type=question, help="a question in French")
    ask.add_argument("--no-rerank", action="store_true", help="without the reranker")
    ask.add_argument(
        "--today",
        type=date.fromisoformat,
        help="the day the question is asked (YYYY-MM-DD), today by default",
    )
    ask.set_defaults(run=_ask)
