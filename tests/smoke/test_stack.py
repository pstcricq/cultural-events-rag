"""Smoke tests of the services: the API and the web interface answer, and the
interface reaches the API by its service name."""

from collections.abc import Callable

import httpx

from cultural_events_rag.api.schemas import HealthResponse, MetadataResponse
from cultural_events_rag.constants import CITY
from tests.smoke.conftest import API_URL, UI_URL


def test_the_api_says_whether_it_can_answer() -> None:
    response = httpx.get(f"{API_URL}/health", timeout=10)

    health = HealthResponse.model_validate(response.json())
    # 503 without an index or with dummy keys: the server answers.
    assert response.status_code == (200 if health.status == "ok" else 503)


def test_the_api_gives_its_metadata() -> None:
    response = httpx.get(f"{API_URL}/metadata", timeout=10)

    assert response.status_code == 200, response.text
    assert MetadataResponse.model_validate(response.json()).city == CITY


def test_the_web_interface_is_up() -> None:
    response = httpx.get(f"{UI_URL}/_stcore/health", timeout=10)

    assert response.status_code == 200
    assert response.text == "ok"


def test_the_web_interface_reaches_the_api_by_its_name(
    run_in_ui: Callable[[str], str],
) -> None:
    # The client of the web interface, with its API_URL.
    output = run_in_ui(
        "from cultural_events_rag.settings import get_settings\n"
        "from cultural_events_rag.ui.client import ApiClient\n"
        "settings = get_settings()\n"
        "print(settings.api_url, ApiClient(settings.api_url).health().status)"
    )

    assert output.split() in (
        ["http://api:8000", "ok"],
        ["http://api:8000", "unavailable"],
    )
