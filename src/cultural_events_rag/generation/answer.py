"""The answer to a question, written by the chat model from the events found.

The model returns a structured output: its answer and the uids of the events it
recommends. Only the uids of the events it was given are kept, and the details
shown with the answer (dates, place, price, link) come from the index, not from
the generated text."""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field
from tenacity import Retrying

from cultural_events_rag.constants import CITY
from cultural_events_rag.errors import GenerationError
from cultural_events_rag.generation.prompt import (
    PROMPT,
    format_context,
    french_quotes,
)
from cultural_events_rag.indexing.formatting import format_day
from cultural_events_rag.retrieval.search import EventMatch, Retrieval
from cultural_events_rag.retry import make_retrying

logger = logging.getLogger(__name__)

# An answer without its structured output is asked again, up to this many
# attempts.
STRUCTURED_ATTEMPTS = 3


class Recommendation(BaseModel):
    """The structured output of the chat model; the descriptions of its fields
    are instructions to the model, in French."""

    answer: str = Field(description="Réponse à l'utilisateur, en français.")
    event_uids: list[str] = Field(
        default_factory=list,
        description=(
            "uid de tous les événements cités dans la réponse, du plus au moins "
            "pertinent. Liste vide si aucun événement ne convient."
        ),
    )


@dataclass(frozen=True)
class Answer:
    """The answer to a question, the events it recommends, and the search it
    was written from."""

    text: str
    events: list[EventMatch]  # recommended by the model, the most relevant first
    retrieval: Retrieval


def recommender(llm: BaseChatModel) -> Runnable[Any, Any]:
    """Return ``llm`` with a ``Recommendation`` as structured output, as JSON
    constrained by its schema."""
    return llm.with_structured_output(Recommendation, method="json_schema")


def strip_markdown_emphasis(text: str) -> str:
    """Remove the Markdown emphasis (**bold**, __bold__, *italic*) from
    ``text``. A lone asterisk ("2 * 3") is kept."""
    text = re.sub(r"(\*\*|__)(\S(?:.*?\S)?)\1", r"\2", text)
    return re.sub(r"\*(\S(?:.*?\S)?)\*", r"\1", text)


# The endings of a whole answer; a colon announces a list.
_SENTENCE_ENDS = (".", "!", "?", "…", "»", ")")


def looks_cut(text: str) -> bool:
    """Return whether ``text`` stops in the middle of a sentence. A Markdown
    mark after the last word ("annulé.*") is ignored."""
    return not text.rstrip().rstrip("*_").rstrip().endswith(_SENTENCE_ENDS)


def generate(
    model: Runnable[Any, Any],
    question: str,
    today: date,
    retrieval: Retrieval,
    retrying: Retrying | None = None,
) -> Answer:
    """Return the answer of ``model``, a ``recommender``, to ``question`` asked
    on ``today``, from the events of ``retrieval``."""
    chain = PROMPT | model
    inputs = {
        "city": CITY,
        "today": format_day(today),
        "context": format_context(retrieval.matches),
        "question": french_quotes(question),
    }
    retrying = retrying or make_retrying("Generation")
    for attempt in range(1, STRUCTURED_ATTEMPTS + 1):
        output = retrying(chain.invoke, inputs)
        if output is not None:
            break
        logger.warning(
            "No structured answer from the model (%d/%d)", attempt, STRUCTURED_ATTEMPTS
        )
    else:
        raise GenerationError(
            f"no structured answer from the model after {STRUCTURED_ATTEMPTS} attempts"
        )
    recommendation = Recommendation.model_validate(output)

    by_uid = {match.uid: match for match in retrieval.matches}
    unknown = [uid for uid in recommendation.event_uids if uid not in by_uid]
    if unknown:
        logger.warning("Uids not given to the model, left out: %s", ", ".join(unknown))
    events = [
        by_uid[uid]
        for uid in dict.fromkeys(recommendation.event_uids)  # once each, in order
        if uid in by_uid
    ]
    if looks_cut(recommendation.answer):
        logger.warning("The answer looks cut off: %r", recommendation.answer[-60:])
    return Answer(
        text=strip_markdown_emphasis(recommendation.answer),
        events=events,
        retrieval=retrieval,
    )
