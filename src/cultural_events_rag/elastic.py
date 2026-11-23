"""The Elasticsearch client and the alias the index of the events is served under."""

from elasticsearch import Elasticsearch

from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.settings import Settings


def make_elastic_client(settings: Settings) -> Elasticsearch:
    """Return a client of the Elasticsearch of ``settings``. It connects at its
    first request."""
    if not settings.elasticsearch_url:
        raise MissingSettingError("ELASTICSEARCH_URL is not set: add it to .env")
    if not settings.elastic_user:
        raise MissingSettingError("ELASTIC_USER is not set: add it to .env")
    if not settings.elastic_password:
        raise MissingSettingError("ELASTIC_PASSWORD is not set: add it to .env")
    return Elasticsearch(
        settings.elasticsearch_url,
        basic_auth=(
            settings.elastic_user,
            settings.elastic_password.get_secret_value(),
        ),
        request_timeout=30,
    )


def index_alias(settings: Settings) -> str:
    """Return the alias the index of the events is served under."""
    if not settings.elasticsearch_index:
        raise MissingSettingError("ELASTICSEARCH_INDEX is not set: add it to .env")
    return settings.elasticsearch_index
