"""The Elasticsearch of the integration tests: a container of
``ELASTIC_VERSION``, started by testcontainers once per session on a free port,
with security on, and removed at the end. Without Docker the tests are skipped,
and fail under CI. ``settings`` points at it with an alias per test; ``client``
reaches it."""

import os
import shutil
import uuid
from collections.abc import Iterator

import pytest
from elasticsearch import Elasticsearch
from pydantic import SecretStr
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import (
    CompositeWaitStrategy,
    HttpWaitStrategy,
)

from cultural_events_rag.elastic import make_elastic_client
from cultural_events_rag.settings import Settings
from tests import elastic_version

IMAGE = f"docker.elastic.co/elasticsearch/elasticsearch:{elastic_version()}"
PASSWORD = "integration-tests"

# Ready once the cluster answers yellow to the elastic user and refuses a wrong
# password with a 401.
READY = CompositeWaitStrategy(
    HttpWaitStrategy(9200, "/_cluster/health?wait_for_status=yellow&timeout=1s")
    .with_basic_credentials("elastic", PASSWORD)
    .for_status_code(200)
    .with_startup_timeout(120),
    HttpWaitStrategy(9200, "/")
    .with_basic_credentials("elastic", "not-the-password")
    .for_status_code(401)
    .with_startup_timeout(120),
)


@pytest.fixture(scope="session")
def elasticsearch_url() -> Iterator[str]:
    if shutil.which("docker") is None:
        if os.environ.get("CI"):
            pytest.fail("no docker under CI for Elasticsearch")
        pytest.skip("no docker for Elasticsearch")
    container = (
        DockerContainer(IMAGE)
        .with_exposed_ports(9200)
        .with_envs(
            **{
                "discovery.type": "single-node",
                "ELASTIC_PASSWORD": PASSWORD,
                "xpack.security.http.ssl.enabled": "false",
                "xpack.ml.enabled": "false",
                "ES_JAVA_OPTS": "-Xms512m -Xmx512m",
            }
        )
        .waiting_for(READY)
    )
    container.start()
    try:
        host, port = container.get_container_host_ip(), container.get_exposed_port(9200)
        yield f"http://{host}:{port}"
    finally:
        container.stop()


@pytest.fixture
def settings(elasticsearch_url: str) -> Settings:
    """Return the settings of the test Elasticsearch, an alias per test, no reranker."""
    return Settings(
        _env_file=None,
        elasticsearch_url=elasticsearch_url,
        elastic_user="elastic",
        elastic_password=SecretStr(PASSWORD),
        elasticsearch_index=f"events-test-{uuid.uuid4().hex[:8]}",
        rerank_available=False,  # no model in the tests: a fake one where needed
        llm_requests_per_minute=2,
    )


@pytest.fixture
def client(settings: Settings) -> Elasticsearch:
    return make_elastic_client(settings)
