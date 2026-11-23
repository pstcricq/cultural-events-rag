"""The tests: ``unit`` needs only the repository, ``integration`` a Docker
daemon for its Elasticsearch, ``smoke`` the services of docker compose running."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def elastic_version() -> str:
    """Return the version of the Elastic images, from .env.example."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    versions: list[str] = re.findall(r"^ELASTIC_VERSION=(.+)$", example, re.MULTILINE)
    return versions[0]
