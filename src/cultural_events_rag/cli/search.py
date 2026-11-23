"""The ``cultural-events-rag search`` command: the filters of a question, and
the events of the index served they keep that are closest to it."""

import argparse
import sys
import time
from datetime import date, datetime
from typing import get_args

import httpx
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.cli.output import question, quiet_logs
from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.elastic import index_alias, make_elastic_client
from cultural_events_rag.errors import MissingModelError, MissingSettingError
from cultural_events_rag.indexing.documents import PRICE_LABELS
from cultural_events_rag.indexing.formatting import format_day, format_time
from cultural_events_rag.mistral import make_embeddings
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import (
    SEARCH_K,
    EventMatch,
    Retrieval,
    SearchMode,
    first_slot,
    index_problem,
    retrieve,
)
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import get_settings


def _block(
    rank: int,
    match: EventMatch,
    filters: SearchFilters,
    mode: SearchMode,
) -> str:
    """Three lines per event: its title; its place, slot and price, as a user
    reads them; what ranked it."""
    metadata = match.chunk.metadata
    place = where_and_when(match, filters)
    lists = ", ".join(
        f"{name} {position}"
        for name, position in match.ranks.items()
        if name != "hybrid"
    )
    trace = (
        f"score {match.score:.3g}, {lists}, "
        f"event {match.uid}, chunk {metadata['chunk_index']}"
    )
    return f"{rank:>2}. {metadata['title']}\n    {place}\n    {trace}\n"


def where_and_when(match: EventMatch, filters: SearchFilters) -> str:
    """Its place, its first slot in the period of the filters and its price,
    as a user reads them."""
    metadata = match.chunk.metadata
    slot = first_slot(match, filters)
    when = f"{format_day(slot.date())} à {format_time(slot)}"
    is_free = metadata["is_free"]
    price = PRICE_LABELS[is_free] if is_free is not None else "tarif non précisé"
    return ", ".join(part for part in (metadata["venue"], when, price) if part)


def _search(args: argparse.Namespace) -> int:
    settings = get_settings()
    quiet_logs()
    url = settings.elasticsearch_url
    mode: SearchMode = args.mode
    k: int = args.k or SEARCH_K
    today: date = args.today or datetime.now(TIMEZONE).date()
    try:
        alias = index_alias(settings)
        client = make_elastic_client(settings)
        embeddings = make_embeddings(settings) if mode != "lexical" else None
        problem = index_problem(client, settings)
        if problem:
            print(f"FAIL {problem}", file=sys.stderr)
            return 1
        start = time.perf_counter()
        retrieval: Retrieval = retrieve(
            client, alias, args.question, today, mode, k, embeddings
        )
        elapsed = time.perf_counter() - start
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
        print(f"FAIL embedding the question: {describe(exc)}", file=sys.stderr)
        return 1

    search = f"{mode} search"
    print(f"Question: {args.question}")
    events = f"{k} event" + ("s" if k > 1 else "")
    print(f"Asked on {today}, {search}, {events} at most, {elapsed:.1f} s")
    print(f"Filters: {retrieval.filters.describe()}\n")
    if not retrieval.matches:
        print("No event")
    for rank, match in enumerate(retrieval.matches, 1):
        print(_block(rank, match, retrieval.filters, mode))
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag search`` to the cultural-events-rag command."""
    search = commands.add_parser(
        "search", help="the events of the index closest to a question"
    )
    search.add_argument("question", type=question, help="a question in French")
    search.add_argument(
        "--mode",
        choices=get_args(SearchMode),
        required=True,
        help="how to rank the events: by their words, their vector, or both",
    )
    search.add_argument("--k", type=int, help="events kept, default: SEARCH_K (5)")
    search.add_argument(
        "--today",
        type=date.fromisoformat,
        help="the day the question is asked (YYYY-MM-DD), today by default",
    )
    search.set_defaults(run=_search)
