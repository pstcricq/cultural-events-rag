"""The services of docker compose, checked from outside. The tests stop at
once, saying what to start, when the services do not answer. They never call
Mistral."""

import subprocess
from collections.abc import Callable

import httpx
import pytest

from tests import ROOT

# The ports compose.yaml publishes.
API_URL = "http://127.0.0.1:8000"
UI_URL = "http://127.0.0.1:8501"


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    """Keep the environment of the machine, for docker compose."""


@pytest.fixture(scope="session", autouse=True)
def services_running() -> None:
    """Stop the session, saying what to start, when the API or the web
    interface does not answer."""
    for name, url in (("API", API_URL), ("web interface", UI_URL)):
        try:
            httpx.get(url, timeout=5)
        except httpx.TransportError:
            pytest.exit(
                f"The {name} does not answer at {url}: start the services with "
                'make docker-up S="api ui", then run make test-smoke again.',
                returncode=1,
            )


@pytest.fixture
def run_in_ui() -> Callable[[str], str]:
    """Return a function running a Python snippet in the container of the web
    interface: its output, or the test fails with its error."""

    def run(code: str) -> str:
        done = subprocess.run(
            ["docker", "compose", "exec", "-T", "ui", "python", "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if done.returncode:
            pytest.fail(f"docker compose exec ui failed: {done.stderr.strip()}")
        return done.stdout.strip()

    return run
