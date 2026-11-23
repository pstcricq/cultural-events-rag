"""The Streamlit page: a chat with the assistant, through the API.

    uv run streamlit run src/cultural_events_rag/ui/app.py

Each question is answered on its own; the chat only keeps the previous answers
on screen."""

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime

import streamlit as st

from cultural_events_rag.api.schemas import (
    MAX_QUESTION_LENGTH,
    AskResponse,
    HealthResponse,
    MetadataResponse,
    RecommendedEvent,
)
from cultural_events_rag.constants import CITY, TIMEZONE
from cultural_events_rag.indexing.formatting import format_day
from cultural_events_rag.settings import get_settings
from cultural_events_rag.ui.client import ApiClient, ApiError
from cultural_events_rag.ui.text import (
    ABOUT,
    EXAMPLE_QUESTIONS,
    audience,
    day_tile,
    delay,
    describe_filters,
    error_message,
    price_badge,
    waiting_message,
    when,
)

# The width of the sidebar, in pixels.
SIDEBAR_WIDTH = 400

# The pause between two words of a streamed answer, in seconds.
STREAM_DELAY = 0.02
# The colours of the day tile, from the theme of the page.
TILE_STYLE = (
    "background:#FBF1E8;color:#9A3412;border-radius:0.75rem;text-align:center;"
    "padding:0.5rem 0;max-width:4.5rem;line-height:1.2"
)
TIME_STYLE = (
    "border-top:1px solid #EADFD3;margin:0.4rem 0.6rem 0;padding-top:0.3rem;"
    "font-size:0.85rem;color:#C2410C"
)

# The avatar of each side of the chat.
AVATARS = {"user": ":material/person:", "assistant": ":material/theater_comedy:"}


@dataclass(frozen=True)
class Message:
    role: str  # "user" or "assistant"
    text: str
    response: AskResponse | None = None
    detail: str | None = None  # the error of the API, when it failed


@st.cache_resource
def get_client() -> ApiClient:
    """Return the client of the API at ``API_URL``; raise ``ApiError`` when it
    is unset."""
    url = get_settings().api_url
    if not url:
        raise ApiError(None, "API_URL is not set: add it to .env")
    return ApiClient(url)


@st.cache_data(ttl=30, show_spinner=False)
def get_health() -> HealthResponse:
    return get_client().health()


@st.cache_data(ttl=30, show_spinner=False)
def get_metadata() -> MetadataResponse:
    return get_client().metadata()


def today() -> date:
    return datetime.now(TIMEZONE).date()


def markdown(text: str) -> str:
    """Escape ``$`` in plain text shown as Markdown, which would start a formula."""
    return text.replace("$", r"\$")


def words(text: str) -> Iterator[str]:
    """Yield the words of ``text`` one by one, each with the spaces before it."""
    for word in re.findall(r"\s*\S+", text):
        time.sleep(STREAM_DELAY)
        yield word


def render_day_tile(event: RecommendedEvent) -> None:
    """Show the tile of the first slot in the period of the question: its day,
    large, then its time. The HTML holds no text of the event."""
    weekday, day, month, time = day_tile(event.next_slot)
    st.html(
        f'<div style="{TILE_STYLE}"><div style="font-size:0.8rem">{weekday}</div>'
        f'<div style="font-size:1.6rem;font-weight:700;color:#C2410C">{day}</div>'
        f'<div style="font-size:0.8rem">{month}</div>'
        f'<div style="{TIME_STYLE}">{time}</div></div>'
    )


def badge(text: str, color: str, icon: str) -> str:
    """Return a Streamlit Markdown badge, its text escaped."""
    text = markdown(text).replace("[", r"\[").replace("]", r"\]")
    return f":{color}-badge[{icon} {text}]"


def render_event(event: RecommendedEvent, today: date) -> None:
    with st.container(border=True):
        tile, details = st.columns([1, 7])
        with tile:
            render_day_tile(event)
        with details:
            render_event_details(event, today)


def render_event_details(event: RecommendedEvent, today: date) -> None:
    """Show the title, the badges, the slots or dates, and the place, one per
    line, then the link across the whole width."""
    label, color = price_badge(event.is_free)
    badges = [badge(label, color, ":material/euro_symbol:")]
    if soon := delay(event.next_slot, today):
        badges.append(badge(soon, "orange", ":material/event_upcoming:"))
    if event.district:
        badges.append(badge(event.district, "gray", ":material/location_city:"))
    if ages := audience(event.age_min, event.age_max):
        badges.append(badge(ages, "gray", ":material/family_restroom:"))
    one_day, dates = when(event.next_slot, event.dates)
    icon = ":material/schedule:" if one_day else ":material/calendar_month:"
    place = " · ".join(part for part in (event.venue, event.address) if part)
    with st.container(gap="xxsmall"):
        st.markdown(f"##### {markdown(event.title)}")
        st.markdown(" ".join(badges))
        st.caption(f"{icon} {markdown(dates)}")
        if place:
            st.caption(f":material/location_on: {markdown(place)}")
    if event.url:
        st.link_button(
            "Voir l'événement",
            event.url,
            icon=":material/open_in_new:",
            width="stretch",
        )


def render_response(response: AskResponse, *, stream: bool = False) -> None:
    if stream:
        st.write_stream(words(markdown(response.answer)))
    else:
        st.markdown(markdown(response.answer))
    for event in response.events:
        render_event(event, response.today)
    understood = describe_filters(response.filters, response.today)
    if response.today != today():
        understood.insert(0, f"Date simulée : {format_day(response.today)}")
    if understood:
        st.caption(f":material/filter_alt: {' · '.join(understood)}")


def render(message: Message, *, stream: bool = False) -> None:
    """Show a message of the chat; with ``stream``, an answer is written word
    by word."""
    with st.chat_message(message.role, avatar=AVATARS[message.role]):
        if message.response:
            render_response(message.response, stream=stream)
        elif message.detail is not None:
            st.error(message.text)
            st.caption(markdown(message.detail))
        else:
            st.markdown(markdown(message.text))


def answer(question: str, day: date | None) -> Message:
    try:
        response = get_client().ask(question, day)
    except ApiError as exc:
        return Message("assistant", error_message(exc), detail=exc.detail)
    return Message("assistant", response.answer, response=response)


def note(text: str) -> None:
    """Show a small line of the sidebar in the colour of the text."""
    st.markdown(f":small[{markdown(text)}]")


def render_health() -> bool:
    """Show the state of the assistant, or that the API does not answer."""
    try:
        health = get_health()
    except ApiError as exc:
        st.error(error_message(exc), icon=":material/cloud_off:")
        note(exc.detail)
        return False
    with st.container(border=True):
        if health.status == "ok":
            st.markdown(":green[:material/check_circle:] **Prêt à répondre**")
        else:
            st.markdown(":orange[:material/warning:] **Indisponible**")
            note(health.detail or "")
    return True


def render_metadata(metadata: MetadataResponse) -> None:
    index = metadata.index
    if index is None:
        note("Aucun index des événements pour le moment.")
    else:
        st.markdown(f"**{index.events}** événements culturels à {metadata.city}")
        if index.built_at:
            built = index.built_at.astimezone(TIMEZONE).date()
            note(f"Agenda mis à jour le {format_day(built)}")
    if metadata.rebuild.state == "running":
        st.info("Mise à jour de l'agenda en cours…", icon=":material/sync:")
    with st.expander("Détails techniques"):
        rate = metadata.llm_requests_per_minute
        reranker = f"`{metadata.rerank_model}`" if metadata.rerank_model else "aucun"
        lines = [
            f"Génération : `{metadata.llm_model}`, {rate:g} questions par minute",
            f"Recherche : `{metadata.search_mode}`, {metadata.search_k} "
            + "événements transmis au modèle",
            f"Embeddings : `{metadata.embedding_model}`",
            f"Reranker : {reranker}",
        ]
        if index is not None:
            lines.append(f"Index : `{index.index}`, {index.documents} extraits")
        st.markdown("\n".join(f"- {line}" for line in lines))


def sidebar() -> tuple[MetadataResponse | None, date | None]:
    """Show the sidebar; return the metadata (None when the API cannot give
    them) and the day chosen to ask on, if any."""
    metadata = None
    with st.sidebar:
        st.header("Assistant culturel", anchor=False)
        if render_health():
            try:
                metadata = get_metadata()
            except ApiError:
                pass  # the state above already says why
        if metadata:
            render_metadata(metadata)
        st.divider()
        simulated = st.toggle(
            "Simuler une autre date",
            help="Pour poser une question comme un autre jour.",
        )
        chosen = st.date_input(
            "Date du jour", value=today(), format="DD/MM/YYYY", disabled=not simulated
        )
        st.divider()
        st.button("Nouvelle conversation", icon=":material/refresh:", on_click=clear)
        st.divider()
        st.markdown("**À propos**")
        note(ABOUT)
    return metadata, chosen if simulated and isinstance(chosen, date) else None


def ask_example(question: str) -> None:
    st.session_state.pending = question


def clear() -> None:
    st.session_state.messages = []


def main() -> None:
    st.set_page_config(
        page_title="Assistant culturel",
        page_icon="🎭",
        initial_sidebar_state=SIDEBAR_WIDTH,
    )
    messages: list[Message] = st.session_state.setdefault("messages", [])
    metadata, day = sidebar()

    st.title(f"Que faire à {metadata.city if metadata else CITY} ?", anchor=False)
    st.caption(
        "Posez une question sur les événements culturels : l'assistant répond "
        "à partir des agendas de la ville. Chaque question est traitée à part. "
        "Réponses indicatives, à vérifier sur la page de chaque événement."
    )
    # Pinned to the bottom of the page, wherever it is called.
    question = st.chat_input(
        "Votre question…", max_chars=MAX_QUESTION_LENGTH
    ) or st.session_state.pop("pending", None)
    if not messages and not question:
        st.markdown("**Exemples de questions**")
        columns = st.columns(2)
        for number, (example, icon) in enumerate(EXAMPLE_QUESTIONS):
            columns[number % 2].button(
                example,
                icon=icon,
                width="stretch",
                on_click=ask_example,
                args=(example,),
            )

    for message in messages:
        render(message)

    if isinstance(question, str):
        asked = Message("user", question)
        render(asked)
        rate = metadata.llm_requests_per_minute if metadata else None
        with st.spinner(waiting_message(rate)):
            reply = answer(question, day)
        render(reply, stream=True)
        messages += [asked, reply]


if __name__ == "__main__":
    main()
