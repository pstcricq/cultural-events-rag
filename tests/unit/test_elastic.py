"""The client of the search engine made from the settings: their URL, user and
password, a missing one refused; and the alias of the index."""

import base64

import pytest
from elasticsearch import Elasticsearch
from pydantic import SecretStr

from cultural_events_rag.elastic import index_alias, make_elastic_client
from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.settings import Settings

URL = "http://127.0.0.1:9200"


def test_a_missing_url_is_refused() -> None:
    settings = Settings(
        _env_file=None, elastic_user="elastic", elastic_password=SecretStr("secret")
    )

    with pytest.raises(MissingSettingError, match="ELASTICSEARCH_URL"):
        make_elastic_client(settings)


@pytest.mark.parametrize("user", [None, ""])
def test_a_missing_user_is_refused(user: str | None) -> None:
    settings = Settings(
        _env_file=None,
        elasticsearch_url=URL,
        elastic_user=user,
        elastic_password=SecretStr("secret"),
    )

    with pytest.raises(MissingSettingError, match="ELASTIC_USER"):
        make_elastic_client(settings)


@pytest.mark.parametrize("password", [None, SecretStr("")])
def test_a_missing_password_is_refused(password: SecretStr | None) -> None:
    settings = Settings(
        _env_file=None,
        elasticsearch_url=URL,
        elastic_user="elastic",
        elastic_password=password,
    )

    with pytest.raises(MissingSettingError, match="ELASTIC_PASSWORD"):
        make_elastic_client(settings)


def test_the_client_reaches_the_url_of_the_settings_as_their_user() -> None:
    settings = Settings(
        _env_file=None,
        elasticsearch_url="http://search:9201",
        elastic_user="reader",
        elastic_password=SecretStr("secret"),
    )

    client = make_elastic_client(settings)

    assert isinstance(client, Elasticsearch)
    assert client.transport.node_pool.get().base_url == "http://search:9201"
    authorization = client._headers["authorization"]
    assert authorization == "Basic " + base64.b64encode(b"reader:secret").decode()


def test_the_alias_of_the_index_is_that_of_the_settings() -> None:
    settings = Settings(_env_file=None, elasticsearch_index="events-test")

    assert index_alias(settings) == "events-test"


def test_a_missing_alias_is_refused() -> None:
    with pytest.raises(MissingSettingError, match="ELASTICSEARCH_INDEX"):
        index_alias(Settings(_env_file=None))
