"""How the application reaches Elasticsearch, the search engine holding the
index of the events: the URL of the settings, their user and password. Used to
write the index and to search it."""

from elasticsearch import Elasticsearch

from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.settings import Settings


def make_elastic_client(settings: Settings) -> Elasticsearch:
    """A client of the Elasticsearch of the settings; it connects at its first
    request."""
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
