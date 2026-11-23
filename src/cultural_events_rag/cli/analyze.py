"""The ``cultural-events-rag analyze`` command: the filters a question gives,
the districts and venues read from the index served."""

import argparse
import sys
from datetime import date, datetime

from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.cli.output import question
from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.elastic import index_alias, make_elastic_client
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.indexing.store import served_indices
from cultural_events_rag.retrieval.query_analysis import PlaceMatcher, analyze
from cultural_events_rag.settings import get_settings


def _analyze(args: argparse.Namespace) -> int:
    settings = get_settings()
    url = settings.elasticsearch_url
    try:
        alias = index_alias(settings)
        client = make_elastic_client(settings)
        if not served_indices(client, alias):
            print(f"FAIL no index behind {alias}: run make index", file=sys.stderr)
            return 1
        places = PlaceMatcher.from_index(client, alias)
    except MissingSettingError as exc:
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

    today = args.today or datetime.now(TIMEZONE).date()
    filters = analyze(args.question, today, places)
    districts = len(set(places.districts.values()))
    print(f"Question: {args.question}")
    print(f"Today: {today}, places: {districts} districts, {len(places.venues)} venues")
    print(f"\nFilters: {filters.describe()}")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag analyze`` to the cultural-events-rag command."""
    analyze_ = commands.add_parser(
        "analyze", help="the filters a question gives: period, free entry, place"
    )
    analyze_.add_argument("question", type=question, help="a question in French")
    analyze_.add_argument(
        "--today",
        type=date.fromisoformat,
        help="the day the question is asked (YYYY-MM-DD), today by default",
    )
    analyze_.set_defaults(run=_analyze)
