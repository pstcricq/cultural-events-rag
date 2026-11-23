"""What the API serves: the assistant of assistant.py, loaded once at start,
and the rebuild of its index.

The work stays in the packages of each step (collection, indexing,
retrieval, generation) and in the assistant that puts them together: this
module keeps it loaded, and runs the rebuild in the background. The new index replaces the one served only
once complete (the alias moves), so the questions keep their answers
meanwhile, and a failed rebuild leaves it in place.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx
from elasticsearch import Elasticsearch

from cultural_events_rag.api.schemas import IndexState, RebuildState
from cultural_events_rag.assistant import Assistant, load_assistant
from cultural_events_rag.collection.fetch import (
    LOOKBACK_DAYS,
    event_cap,
    fetch_agendas,
    select_source,
)
from cultural_events_rag.collection.files import save_events, save_raw
from cultural_events_rag.collection.process import process_events
from cultural_events_rag.constants import CITY, CULTURAL_AGENDAS
from cultural_events_rag.errors import (
    MissingModelError,
    MissingSettingError,
    RerankerError,
    SourceError,
)
from cultural_events_rag.generation.answer import Answer
from cultural_events_rag.indexing.build import build_index
from cultural_events_rag.indexing.store import indexed_uids, served_index
from cultural_events_rag.mistral import make_embeddings
from cultural_events_rag.paths import EVENTS_FILE, RAW_DIR
from cultural_events_rag.retrieval.search import index_problem
from cultural_events_rag.settings import Settings

logger = logging.getLogger(__name__)

# What keeps the assistant from loading: a key, a model or the rerank extra.
LOAD_ERRORS = (MissingSettingError, MissingModelError, RerankerError)


class AssistantUnavailableError(RuntimeError):
    """The assistant could not load: the reason is in the message."""


class RebuildRunningError(RuntimeError):
    """A rebuild is already running."""


def rebuild_index(settings: Settings, client: Elasticsearch) -> int:
    """The events fetched again, processed and indexed, as by make fetch,
    process and index: their count. Nothing replaced without events."""
    now = datetime.now(UTC)
    since = now - timedelta(days=LOOKBACK_DAYS)
    with httpx.Client(timeout=30) as http:
        source = select_source(settings, http)
        cap = event_cap(settings.max_events)
        raw = fetch_agendas(source, CULTURAL_AGENDAS, CITY, since, cap)
    save_raw(raw, RAW_DIR / f"{source.name}.json")
    report = process_events(raw, source.name, CULTURAL_AGENDAS, CITY, since, now)
    if not report.events:
        raise SourceError("no event fetched: the index served is kept")
    save_events(report.events, EVENTS_FILE)
    build_index(client, report.events, make_embeddings(settings), settings)
    return len(report.events)


class AssistantService:
    """The assistant served, and the state of the rebuild of its index."""

    def __init__(
        self,
        settings: Settings,
        load: Callable[[Settings], Assistant] = load_assistant,
        rebuild: Callable[[Settings, Elasticsearch], int] = rebuild_index,
    ) -> None:
        self.settings = settings
        self._load, self._rebuild = load, rebuild
        self._assistant: Assistant | None = None
        self.unavailable: str | None = "the assistant is not loaded yet"
        self.rebuild_state = RebuildState(state="idle")
        self._rebuilding = threading.Lock()

    def start(self) -> None:
        """Load the assistant. Without a key or a model, the API starts all
        the same and says why on /health."""
        try:
            self._assistant = self._load(self.settings)
        except LOAD_ERRORS as exc:
            self.unavailable = str(exc)
            logger.error("Assistant unavailable: %s", exc)
            return
        self.unavailable = None
        logger.info("Assistant loaded")

    @property
    def assistant(self) -> Assistant:
        if self._assistant is None:
            raise AssistantUnavailableError(self.unavailable)
        return self._assistant

    def problem(self) -> str | None:
        """Why no question can be answered: the assistant not loaded, no
        index or an outdated one; None when one can."""
        if self._assistant is None:
            return self.unavailable
        return index_problem(self._assistant.client, self.settings)

    def ask(self, question: str, today: date) -> Answer:
        """The answer to ``question`` asked on ``today``."""
        return self.assistant.ask(question, today)

    def index_state(self) -> IndexState | None:
        """The index served: None before the first build."""
        client, alias = self.assistant.client, self.assistant.index
        info = served_index(client, alias)
        if info is None:
            return None
        built_at = info.meta.get("built_at")
        return IndexState(
            alias=alias,
            index=info.name,
            events=len(indexed_uids(client, info.name, info.count)),
            documents=info.count,
            built_at=datetime.fromisoformat(built_at) if built_at else None,
        )

    def start_rebuild(self) -> None:
        """Mark a rebuild as started: ``RebuildRunningError`` when one runs
        already. ``rebuild`` then runs it."""
        if not self._rebuilding.acquire(blocking=False):
            raise RebuildRunningError("a rebuild is already running")
        self.rebuild_state = RebuildState(
            state="running", started_at=datetime.now(UTC).replace(microsecond=0)
        )

    def rebuild(self) -> None:
        """Rebuild the index, as started by ``start_rebuild``: its outcome in
        ``rebuild_state``, never raised (it runs in the background)."""
        state = self.rebuild_state
        try:
            events = self._rebuild(self.settings, self.assistant.client)
        except Exception as exc:  # noqa: BLE001 (in the background: kept, logged)
            logger.error("Rebuild failed: %s", exc)
            self.rebuild_state = state.model_copy(
                update={"state": "failed", "detail": str(exc), "finished_at": _now()}
            )
        else:
            logger.info("Rebuild done: %d events", events)
            self.rebuild_state = state.model_copy(
                update={"state": "done", "events": events, "finished_at": _now()}
            )
        finally:
            self._rebuilding.release()


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
