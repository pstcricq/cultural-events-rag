"""The client of the settings against a real Elasticsearch: the version of
.env.example with the right password, a refusal with a wrong one."""

import pytest
from elasticsearch import AuthenticationException
from pydantic import SecretStr

from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.settings import Settings
from tests import ROOT


def test_the_engine_is_the_version_of_the_example(settings: Settings) -> None:
    version = make_elastic_client(settings).info()["version"]["number"]

    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert f"ELASTIC_VERSION={version}\n" in example


def test_a_wrong_password_is_refused(settings: Settings) -> None:
    wrong = settings.model_copy(update={"elastic_password": SecretStr("wrong")})

    with pytest.raises(AuthenticationException):
        make_elastic_client(wrong).info()
