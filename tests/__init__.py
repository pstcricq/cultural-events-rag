"""The tests: unit/ needs nothing but the repository, integration/ a docker
that runs the Elasticsearch of compose.yaml, smoke/ the services `make
docker-up` started."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def elastic_version() -> str:
    """The version of the Elastic images, set in .env.example."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    versions: list[str] = re.findall(r"^ELASTIC_VERSION=(.+)$", example, re.MULTILINE)
    return versions[0]
