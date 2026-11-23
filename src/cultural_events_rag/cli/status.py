"""The ``cultural-events-rag status`` command: the index the alias serves, and
whether the code still builds it the same way."""

import argparse
import sys

from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as EngineConnectionError

from cultural_events_rag.elastic import index_alias, make_elastic_client
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.indexing.build import index_signature
from cultural_events_rag.indexing.store import served_index, signature_differences
from cultural_events_rag.settings import get_settings


def _status(args: argparse.Namespace) -> int:
    settings = get_settings()
    url = settings.elasticsearch_url
    try:
        alias = index_alias(settings)
        client = make_elastic_client(settings)
        version = client.info()["version"]["number"]
        info = served_index(client, alias)
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

    print(f"Elasticsearch: {url} (version {version})")
    if info is None:
        print(f"FAIL no index behind {alias}: run make index", file=sys.stderr)
        return 1
    print(f"Index: {alias} -> {info.name}, {info.count} documents")
    print(f"Built: {info.meta.get('built_at')}")
    differences = signature_differences(info.meta, index_signature())
    if differences:
        print(
            f"FAIL outdated: {'; '.join(differences)}: run make index", file=sys.stderr
        )
        return 1
    print("Settings: up to date")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag status`` to the cultural-events-rag command."""
    status = commands.add_parser(
        "status",
        help="the index served, and whether the code still builds it the same way",
    )
    status.set_defaults(run=_status)
