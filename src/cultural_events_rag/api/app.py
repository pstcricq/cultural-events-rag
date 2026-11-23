"""The REST API of the assistant (FastAPI), its documentation at /docs.

    make api
    uv run uvicorn cultural_events_rag.api.app:create_app --factory

The assistant is loaded once, at start. The routes stay thin: the service
(``api.service``) holds the assistant, the packages of each step do the work.
"""

import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

import httpx
from elasticsearch import ApiError, TransportError
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    Security,
    status,
)
from fastapi.security import APIKeyHeader
from uvicorn.logging import DefaultFormatter

from cultural_events_rag.api.schemas import (
    AskRequest,
    AskResponse,
    ErrorResponse,
    HealthResponse,
    MetadataResponse,
    RebuildState,
    RecommendedEvent,
)
from cultural_events_rag.api.service import (
    AssistantService,
    AssistantUnavailableError,
    RebuildRunningError,
)
from cultural_events_rag.assistant import SEARCH_MODE, reranker_model
from cultural_events_rag.constants import CITY, TIMEZONE
from cultural_events_rag.errors import GenerationError
from cultural_events_rag.indexing.formatting import format_dates
from cultural_events_rag.logs import quiet_libraries
from cultural_events_rag.mistral import (
    EMBEDDING_MODEL,
    LLM_MODEL,
    requests_per_minute,
)
from cultural_events_rag.models import Timing
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import (
    SEARCH_K,
    EventMatch,
    first_slot,
)
from cultural_events_rag.retry import describe
from cultural_events_rag.settings import get_settings

logger = logging.getLogger(__name__)

DESCRIPTION = f"""
Recommends cultural events in {CITY}, from the agendas of the city: the
question is read for its period, place and price, the closest events are
searched in Elasticsearch (lexical, vector, reranked), and a Mistral model
answers in French from those events only.
"""

admin_key = APIKeyHeader(
    name="X-API-Key", auto_error=False, description="The admin key, ADMIN_API_KEY."
)
router = APIRouter()


def get_service(request: Request) -> AssistantService:
    service: AssistantService = request.app.state.service
    return service


Service = Annotated[AssistantService, Depends(get_service)]

# Elasticsearch unreachable, refusing, or failing a request.
ENGINE_ERRORS = (ApiError, TransportError)


def _unavailable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)


def _log_engine(exc: Exception) -> None:
    """The cause of a failure of Elasticsearch, in the logs: its message (an
    address that resolves to no host, a refused connection), which the text
    of the exception leaves out."""
    logger.error("Elasticsearch failed: %s", getattr(exc, "message", exc))


def _engine(exc: Exception) -> HTTPException:
    _log_engine(exc)
    return _unavailable(f"Elasticsearch failed: {type(exc).__name__}")


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": ErrorResponse} for code in codes}


def require_admin(
    service: Service, key: Annotated[str | None, Security(admin_key)]
) -> None:
    """The admin key, in the X-API-Key header."""
    expected = service.settings.admin_api_key
    if expected is None or not expected.get_secret_value():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "rebuild turned off: set ADMIN_API_KEY"
        )
    given = (key or "").encode()
    if not secrets.compare_digest(given, expected.get_secret_value().encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or wrong X-API-Key")


def recommended(match: EventMatch, filters: SearchFilters) -> RecommendedEvent:
    """An event recommended, as the index stores it."""
    metadata = match.chunk.metadata
    timings = [
        Timing(
            begin=datetime.fromisoformat(slot["gte"]),
            end=datetime.fromisoformat(slot["lte"]),
        )
        for slot in metadata["timings"]
    ]
    return RecommendedEvent(
        uid=match.uid,
        title=metadata["title"],
        venue=metadata["venue"],
        address=metadata["address"],
        district=metadata["district"],
        age_min=metadata["age_min"],
        age_max=metadata["age_max"],
        dates=format_dates(timings),
        next_slot=first_slot(match, filters),
        is_free=metadata["is_free"],
        url=metadata["url"],
    )


@router.get(
    "/health",
    summary="Whether the assistant can answer",
    responses={503: {"model": HealthResponse, "description": "It cannot."}},
)
def health(service: Service, response: Response) -> HealthResponse:
    """`ok` when the assistant is loaded and the index served is up to date;
    503 otherwise, with the reason; the cause of a failing Elasticsearch in
    the logs only."""
    try:
        problem = service.problem()
    except ENGINE_ERRORS as exc:
        _log_engine(exc)
        problem = f"Elasticsearch failed: {type(exc).__name__}"
    if problem is None:
        return HealthResponse(status="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="unavailable", detail=problem)


@router.get(
    "/metadata",
    summary="The index served, the models, the last rebuild",
    responses=_errors(503),
)
def metadata(service: Service) -> MetadataResponse:
    settings = service.settings
    try:
        index = service.index_state()
    except AssistantUnavailableError as exc:
        raise _unavailable(f"assistant unavailable: {exc}") from exc
    except ENGINE_ERRORS as exc:
        raise _engine(exc) from exc
    return MetadataResponse(
        city=CITY,
        index=index,
        embedding_model=EMBEDDING_MODEL,
        search_mode=SEARCH_MODE,
        search_k=SEARCH_K,
        rerank_model=reranker_model(settings),
        llm_model=LLM_MODEL,
        llm_requests_per_minute=requests_per_minute(settings),
        rebuild=service.rebuild_state,
    )


@router.post(
    "/ask", summary="Ask the assistant a question", responses=_errors(502, 503)
)
def ask(body: AskRequest, service: Service) -> AskResponse:
    """The answer to a question, and the events it recommends. 422: an empty
    or too long question. 503: no assistant, no index, or an outdated one.
    502: Mistral failed after its retries. An answer waits its turn under the
    quota of the Mistral plan: 30 s per answer on the free plan."""
    today = body.today or datetime.now(TIMEZONE).date()
    try:
        problem = service.problem()
        if problem:
            raise _unavailable(problem)
        answer = service.ask(body.question, today)
    except ENGINE_ERRORS as exc:
        raise _engine(exc) from exc
    except httpx.HTTPError as exc:
        logger.error("Mistral failed: %s", describe(exc))
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Mistral failed: {describe(exc)}"
        ) from exc
    except GenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    filters = answer.retrieval.filters
    logger.info(
        "Answered %r (%s): %d events",
        body.question,
        filters.describe(),
        len(answer.events),
    )
    return AskResponse(
        question=body.question,
        today=today,
        answer=answer.text,
        filters=filters,
        events=[recommended(match, filters) for match in answer.events],
    )


@router.post(
    "/rebuild",
    summary="Fetch the events again and rebuild the index, in the background",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
    responses=_errors(401, 403, 409, 503),
)
def rebuild(service: Service, tasks: BackgroundTasks) -> RebuildState:
    """Fetch, process and index the events again, as make fetch, process and
    index do: a few minutes, followed on /metadata. The questions keep their
    answers from the index served until the new one is complete. 409: a
    rebuild is already running."""
    if service.unavailable is not None:
        raise _unavailable(f"assistant unavailable: {service.unavailable}")
    try:
        service.start_rebuild()
    except RebuildRunningError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    tasks.add_task(service.rebuild)
    return service.rebuild_state


def configure_logging() -> None:
    """Our logs formatted as those of uvicorn, the libraries kept quiet."""
    handler = logging.StreamHandler()
    handler.setFormatter(DefaultFormatter("%(levelprefix)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    quiet_libraries()


def create_app(service: AssistantService | None = None) -> FastAPI:
    """The application, around ``service``: that of the settings by default."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging()
        app.state.service.start()
        yield

    app = FastAPI(
        title="Cultural events RAG",
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.service = service or AssistantService(get_settings())
    app.include_router(router)
    return app
