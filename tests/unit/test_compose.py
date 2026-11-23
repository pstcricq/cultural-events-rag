"""compose.yaml writes no value an environment sets: every Elastic image at
ELASTIC_VERSION (Kibana refuses an Elasticsearch of another version), set in
.env.example, the Python client on its major version; every variable of a
container written and required, every port on 127.0.0.1 only."""

import re
from typing import Any

import yaml

from tests import ROOT, elastic_version


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


def test_every_variable_of_a_container_is_written() -> None:
    for name, service in _services("compose.yaml").items():
        for variable, value in (service.get("environment") or {}).items():
            assert value is not None, f"{name}: {variable} passed only when set"


def test_the_variables_of_the_environment_are_required() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    values = re.findall(r"\$\{(\w+)([^}]*)\}", compose)

    assert values
    assert all(rest.startswith((":?", "?")) for _, rest in values), values


def test_every_port_is_published_on_this_machine_only() -> None:
    ports = [
        port
        for service in _services("compose.yaml").values()
        for port in service.get("ports", [])
    ]

    assert ports
    assert all(port.startswith("127.0.0.1:") for port in ports), ports
