"""compose.yaml writes no value an environment sets: every Elastic image at
ELASTIC_VERSION (Kibana refuses an Elasticsearch of another version), set in
.env.example, the Python client on its major version; the API is given every
setting it reads, each written and required; one image for the application,
built by compose.dev.yaml on this machine only, Elasticsearch run here with
the profile search only, every port on 127.0.0.1 only; and the image builds with
the uv pinned by the project."""

import re
from typing import Any

import yaml

from cultural_events_rag.settings import Settings
from tests import ROOT, elastic_version


def _example() -> str:
    return (ROOT / ".env.example").read_text(encoding="utf-8")


def _services(name: str) -> dict[str, Any]:
    services: dict[str, Any] = yaml.safe_load((ROOT / name).read_text())["services"]
    return services


def test_every_elastic_image_has_the_version_of_the_environment() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    tags = re.findall(r"image: docker\.elastic\.co/[^:\s]+:(\S+)", compose)

    assert len(tags) == 3  # elasticsearch, kibana-setup, kibana
    assert all(tag.startswith("${ELASTIC_VERSION:?") for tag in tags), tags
    assert re.fullmatch(r"\d+\.\d+\.\d+", elastic_version())


def test_no_variable_has_a_default() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert not re.findall(r"\$\{\w+:?-", compose)


def test_the_python_client_is_on_the_same_major_version() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    major = elastic_version().split(".")[0]

    assert f'"elasticsearch>={major}.' in pyproject
    assert f"<{int(major) + 1}" in pyproject


def test_the_api_is_given_every_setting_it_reads() -> None:
    environment = _services("compose.yaml")["api"]["environment"]
    settings = {name.upper() for name in Settings.model_fields}

    assert set(environment) == settings


def test_every_variable_of_a_container_is_written() -> None:
    for name, service in _services("compose.yaml").items():
        for variable, value in (service.get("environment") or {}).items():
            assert value is not None, f"{name}: {variable} passed only when set"


def test_the_variables_of_the_environment_are_required() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    values = re.findall(r"\$\{(\w+)([^}]*)\}", compose)

    assert values
    assert all(rest.startswith(":?") for _, rest in values), values


def test_the_application_runs_from_one_image_built_on_this_machine_only() -> None:
    services = _services("compose.yaml")
    application = {"models", "api"}

    images = {services[name]["image"] for name in application}

    assert len(images) == 1
    assert images.pop().startswith("${APP_IMAGE:?")
    assert not any("build" in service for service in services.values())
    # The build, for this machine only: a server reads compose.yaml alone.
    assert _services("compose.dev.yaml") == {"api": {"build": "."}}
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert (
        "docker compose -f compose.yaml -f compose.dev.yaml --profile search\n"
        in makefile
    )


def test_elasticsearch_runs_here_with_the_profile_search_only() -> None:
    services = _services("compose.yaml")
    api = services["api"]

    elastic = {"elasticsearch", "kibana-setup", "kibana"}
    assert {name for name, s in services.items() if "profiles" in s} == elastic
    assert all(services[name]["profiles"] == ["search"] for name in elastic)
    # The API waits for it when it runs here, and reaches it at an address of
    # its own: without the profile, an Elasticsearch run elsewhere.
    assert api["depends_on"]["elasticsearch"]["required"] is False
    url = api["environment"]["ELASTICSEARCH_URL"]
    assert url.startswith("${API_ELASTICSEARCH_URL:?")
    assert "API_ELASTICSEARCH_URL=http://elasticsearch:9200\n" in _example()


def test_every_port_is_published_on_this_machine_only() -> None:
    ports = [
        port
        for service in _services("compose.yaml").values()
        for port in service.get("ports", [])
    ]

    assert ports
    assert all(port.startswith("127.0.0.1:") for port in ports), ports


def test_the_image_builds_with_the_uv_of_the_project() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    [pinned] = re.findall(r'^required-version = "==(.+)"$', pyproject, re.MULTILINE)

    assert f"ghcr.io/astral-sh/uv:{pinned} " in dockerfile
