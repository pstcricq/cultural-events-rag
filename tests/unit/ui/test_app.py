"""The page of the web interface (Streamlit AppTest), its client talking to a
fake API (httpx.MockTransport): the state of the assistant, a question and
its answer with the events, the errors, the date simulated."""

import functools
import json
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

import httpx
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from cultural_events_rag.constants import TIMEZONE
from cultural_events_rag.settings import Settings
from cultural_events_rag.ui import client
from cultural_events_rag.ui.text import ABOUT
from tests import ROOT

APP = str(ROOT / "src" / "cultural_events_rag" / "ui" / "app.py")

METADATA: dict[str, Any] = {
    "city": "Toulouse",
    "index": {
        "alias": "events",
        "index": "events-20261119-080000",
        "events": 189,
        "documents": 288,
        "built_at": "2026-11-19T08:00:00+00:00",
    },
    "embedding_model": "mistral-embed",
    "search_mode": "hybrid",
    "search_k": 5,
    "rerank_model": "BAAI/bge-reranker-v2-m3",
    "llm_model": "ministral-14b-latest",
    "llm_requests_per_minute": 2,
    "rebuild": {"state": "idle"},
}

EVENT: dict[str, Any] = {
    "uid": "1",
    "title": "Concert de jazz",
    "venue": "Le Taquin",
    "address": "23 rue des Amidonniers, Toulouse",
    "district": "Amidonniers",
    "age_min": 6,
    "age_max": None,
    "dates": "du jeudi 1 octobre 2026 au jeudi 31 décembre 2026 (40 créneaux)",
    "next_slot": "2026-11-21T20:30:00+01:00",
    "is_free": None,
    "url": "https://openagenda.com/jazz",
}


def asked(today: str, **filters: Any) -> dict[str, Any]:
    return {
        "question": "Un concert de jazz ?",
        "today": today,
        "answer": "Je vous recommande le Concert de jazz, à 5 $ la place.",
        "filters": filters,
        "events": [EVENT, {**EVENT, "uid": "2", "url": None}],
    }


class FakeApi:
    """The routes of the API, each answering its status and body; the bodies
    of the questions asked."""

    def __init__(self) -> None:
        today = datetime.now(TIMEZONE).date().isoformat()
        self.routes: dict[str, tuple[int, Any]] = {
            "/health": (200, {"status": "ok"}),
            "/metadata": (200, METADATA),
            "/ask": (200, asked(today, date_from=today)),
        }
        self.questions: list[Any] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/ask":
            self.questions.append(json.loads(request.content))
        status, body = self.routes[request.url.path]
        return httpx.Response(status, json=body)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeApi]:
    fake = FakeApi()
    transport = httpx.MockTransport(fake)
    monkeypatch.setattr(
        client, "ApiClient", functools.partial(client.ApiClient, transport=transport)
    )
    settings = Settings(_env_file=None, api_url="http://127.0.0.1:8000")
    monkeypatch.setattr("cultural_events_rag.settings.get_settings", lambda: settings)
    st.cache_resource.clear()
    st.cache_data.clear()
    yield fake
    st.cache_resource.clear()
    st.cache_data.clear()


def run() -> AppTest:
    page = AppTest.from_file(APP, default_timeout=30)
    page.run()
    assert not page.exception
    return page


def markdowns(page: AppTest) -> list[str]:
    return [markdown.value for markdown in page.markdown]


def captions(page: AppTest) -> str:
    return "\n".join(caption.value for caption in page.caption)


def test_the_first_page_shows_the_state_and_the_examples(api: FakeApi) -> None:
    page = run()

    assert page.title[0].value == "Que faire à Toulouse ?"
    assert ":green[:material/check_circle:] **Prêt à répondre**" in markdowns(page)
    assert "**189** événements culturels à Toulouse" in markdowns(page)
    assert "**Exemples de questions**" in markdowns(page)
    assert ":small[Agenda mis à jour le jeudi 19 novembre 2026]" in markdowns(page)
    assert (
        "Reranker : `BAAI/bge-reranker-v2-m3`"
        in page.sidebar.expander[0].markdown[0].value
    )
    assert len(page.button) == 5  # four examples and a new conversation
    assert f":small[{ABOUT}]" in markdowns(page)


def test_an_example_is_answered_with_its_events(api: FakeApi) -> None:
    page = run()

    page.button[0].click().run()

    assert api.questions == [{"question": "Que faire ce week-end en famille ?"}]
    [question, answer] = page.chat_message
    assert question.markdown[0].value == "Que faire ce week-end en famille ?"
    assert answer.markdown[0].value == (
        r"Je vous recommande le Concert de jazz, à 5 \$ la place."
    )
    # One information per line: its title, its badges (its first slot is long
    # past: no delay), its dates and its place.
    assert markdowns(page).count("##### Concert de jazz") == 2
    assert (
        markdowns(page).count(
            ":gray-badge[:material/euro_symbol: Tarif non précisé] "
            ":gray-badge[:material/location_city: Amidonniers] "
            ":gray-badge[:material/family_restroom: Dès 6 ans]"
        )
        == 2
    )
    assert (
        ":material/calendar_month: du jeudi 1 octobre 2026 au jeudi 31 décembre"
        " 2026 (40 créneaux)"
    ) in captions(page)
    assert (
        ":material/location_on: Le Taquin · 23 rue des Amidonniers, Toulouse"
    ) in captions(page)
    # Its first slot in a tile beside each card: its day, then its time.
    tiles = [element.proto.body for element in page.get("html")]
    assert len(tiles) == 2
    assert all(">sam.<" in tile and ">21<" in tile for tile in tiles)
    assert all(">20h30<" in tile for tile in tiles)
    assert len(page.image) == 0  # no image of the events
    assert len(page.get("link_button")) == 1
    assert "Événements à venir" in captions(page)
    assert "**Exemples de questions**" not in markdowns(page)


def test_a_question_typed_is_answered(api: FakeApi) -> None:
    page = run()

    page.chat_input[0].set_value("Un concert de jazz ?").run()

    assert api.questions == [{"question": "Un concert de jazz ?"}]
    assert len(page.chat_message) == 2


def test_the_previous_answers_stay_and_a_new_conversation_clears_them(
    api: FakeApi,
) -> None:
    page = run()
    page.chat_input[0].set_value("Un concert de jazz ?").run()
    page.chat_input[0].set_value("Un autre ?").run()

    assert len(page.chat_message) == 4

    page.sidebar.button[0].click().run()

    assert not page.chat_message


def test_a_refusal_of_the_api_is_explained(api: FakeApi) -> None:
    api.routes["/ask"] = (503, {"detail": "the index served is outdated"})
    page = run()

    page.chat_input[0].set_value("Un concert de jazz ?").run()

    assert page.error[0].value.startswith("L'assistant n'est pas prêt")
    assert "the index served is outdated" in captions(page)


def test_an_assistant_unavailable_says_why(api: FakeApi) -> None:
    api.routes["/health"] = (503, {"status": "unavailable", "detail": "no index"})
    api.routes["/metadata"] = (
        200,
        {
            **METADATA,
            "index": None,
            "rerank_model": None,
            "rebuild": {"state": "running"},
        },
    )
    page = run()

    assert ":orange[:material/warning:] **Indisponible**" in markdowns(page)
    assert ":small[no index]" in markdowns(page)
    assert ":small[Aucun index des événements pour le moment.]" in markdowns(page)
    assert page.sidebar.info[0].value == "Mise à jour de l'agenda en cours…"
    assert "Reranker : aucun" in page.sidebar.expander[0].markdown[0].value


def test_an_api_without_metadata_still_shows_its_state(api: FakeApi) -> None:
    api.routes["/health"] = (503, {"status": "unavailable", "detail": "no engine"})
    api.routes["/metadata"] = (503, {"detail": "Elasticsearch failed"})
    page = run()

    assert ":orange[:material/warning:] **Indisponible**" in markdowns(page)
    assert not page.sidebar.expander
    assert page.title[0].value == "Que faire à Toulouse ?"


def test_an_api_unreachable_is_said_in_the_sidebar_and_the_chat(
    api: FakeApi,
) -> None:
    api.down = True
    page = run()

    assert page.sidebar.error[0].value.startswith("L'assistant est injoignable")
    assert ":small[http://127.0.0.1:8000 unreachable (ConnectError)]" in markdowns(page)

    page.chat_input[0].set_value("Un concert de jazz ?").run()

    assert page.chat_message[1].error[0].value.startswith("L'assistant est injoignable")


def test_a_simulated_day_is_sent_and_shown(api: FakeApi) -> None:
    api.routes["/ask"] = (200, asked("2026-11-19", date_from="2026-11-19"))
    page = run()

    page.sidebar.toggle[0].set_value(True).run()
    page.sidebar.date_input[0].set_value(date(2026, 11, 19)).run()
    page.chat_input[0].set_value("Un concert de jazz ?").run()

    assert api.questions == [
        {"question": "Un concert de jazz ?", "today": "2026-11-19"}
    ]
    assert "Date simulée : jeudi 19 novembre 2026" in captions(page)
    # The delay of each event from the day simulated: Saturday 21 November.
    upcoming = ":orange-badge[:material/event_upcoming: Ce week-end]"
    assert sum(upcoming in text for text in markdowns(page)) == 2


def test_an_unset_api_url_is_said_in_the_sidebar(
    api: FakeApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(_env_file=None)
    monkeypatch.setattr("cultural_events_rag.settings.get_settings", lambda: settings)

    page = run()

    assert "API_URL is not set: add it to .env" in " ".join(markdowns(page))
