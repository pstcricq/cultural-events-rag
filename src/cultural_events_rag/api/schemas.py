"""The request and response bodies of the API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cultural_events_rag.retrieval.filters import SearchFilters

# The maximum length of a question, in characters.
MAX_QUESTION_LENGTH = 500


class AskRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [{"question": "Un concert de jazz ce week-end ?"}]
        },
    )

    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="A question in French, as a user asks it.",
    )
    today: date | None = Field(
        default=None,
        description=(
            "The day the question is asked, to ask it again on a fixed day: "
            "today in Toulouse by default."
        ),
    )


class RecommendedEvent(BaseModel):
    """An event the answer recommends, every field from the index."""

    uid: str
    title: str
    venue: str | None
    address: str | None
    district: str | None = Field(description="Its district of the city, when known.")
    age_min: int | None = Field(description="The youngest age it is for, when given.")
    age_max: int | None = Field(description="The oldest age it is for, when given.")
    dates: str = Field(description="Its dates and times, in French.")
    next_slot: datetime = Field(
        description="Its first slot in the period of the question, in Toulouse time."
    )
    is_free: bool | None = Field(description="Free, paid, or null when unknown.")
    url: str | None


class AskResponse(BaseModel):
    question: str
    today: date = Field(description="The day the question was answered for.")
    answer: str = Field(description="The answer, in French.")
    filters: SearchFilters = Field(
        description="The constraints read in the question, as the search applied them."
    )
    events: list[RecommendedEvent] = Field(
        description="The events the answer recommends, the most relevant first."
    )


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    detail: str | None = Field(default=None, description="Why it is unavailable.")


class IndexState(BaseModel):
    alias: str
    index: str = Field(description="The index the alias serves.")
    events: int
    documents: int = Field(description="The chunks indexed, one vector each.")
    built_at: datetime | None


class RebuildState(BaseModel):
    state: Literal["idle", "running", "done", "failed"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events: int | None = Field(default=None, description="The events indexed.")
    detail: str | None = Field(default=None, description="Why the rebuild failed.")


class MetadataResponse(BaseModel):
    city: str
    index: IndexState | None = Field(description="Null before the first build.")
    embedding_model: str
    search_mode: str
    search_k: int = Field(description="The events found and given to the LLM.")
    rerank_model: str | None
    llm_model: str
    llm_requests_per_minute: float = Field(
        description="The quota of the Mistral plan: answers wait their turn."
    )
    rebuild: RebuildState


class ErrorResponse(BaseModel):
    detail: str
