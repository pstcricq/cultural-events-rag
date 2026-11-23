"""The services of compose.yaml, started by `make docker-up`: the tests of this
directory check them from the outside, as a user would, and fail when they
are not running, with one message: what to start. They never call Mistral:
/ask is left out."""

import subprocess
from collections.abc import Callable

import httpx
import pytest

from tests import ROOT

# Where compose.yaml publishes them on this machine.
API_URL = "http://127.0.0.1:8000"
UI_URL = "http://127.0.0.1:8501"


@pytest.fixture(autouse=True)
def clean_environment() -> None:
    """The environment of the machine kept, over that of tests/conftest.py:
    these tests read no setting, and docker compose reads the values the CI
    sets there."""


@pytest.fixture(scope="session", autouse=True)
def services_running() -> None:
    """Stop at once, with what to do, when the API or the interface does not
    answer, rather than fail each test on its own."""
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
    """A function running a Python snippet in the container of the web
    interface: its output, or the test failed with its error. docker compose
    reads compose.yaml alone, enough to find the container, and its values
    from the environment, then from .env."""

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
