"""The answer to a question, written by the LLM from the events found.

The LLM returns a structured output: its answer and the uids of the events it
recommends. Only the uids of the events it was given are kept, and every
practical detail shown beside the answer (dates, place, price, link) comes from
the index, never from the generated text.

The LLM is told to say when no event fits: the score of the reranker alone
cannot tell an out-of-scope question apart (``reports/retrieval.md``).
"""

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

# The model sometimes answers without its structured output: it is asked again.
STRUCTURED_ATTEMPTS = 3


class Recommendation(BaseModel):
    """The structured output of the LLM: the descriptions of its fields are
    instructions to it, in French."""

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
    events: list[EventMatch]  # recommended by the LLM, the most relevant first
    retrieval: Retrieval


def recommender(llm: BaseChatModel) -> Runnable[Any, Any]:
    """``llm`` returning a ``Recommendation``, as JSON constrained by its
    schema: with a tool call instead, the API failed on long answers."""
    return llm.with_structured_output(Recommendation, method="json_schema")


def strip_markdown_emphasis(text: str) -> str:
    """Without **bold**, __bold__ nor *italic*: the model does not always keep
    to plain text. A lone asterisk ("2 * 3") stays."""
    text = re.sub(r"(\*\*|__)(\S(?:.*?\S)?)\1", r"\2", text)
    return re.sub(r"\*(\S(?:.*?\S)?)\*", r"\1", text)


# How a whole answer ends: a colon announces what is missing.
_SENTENCE_ENDS = (".", "!", "?", "…", "»", ")")


def looks_cut(text: str) -> bool:
    """Whether ``text`` stops in the middle of a sentence, as when a straight
    quote closed the JSON output early (its uids then came out empty). A
    Markdown mark left after the last word ("annulé.*") does not count."""
    return not text.rstrip().rstrip("*_").rstrip().endswith(_SENTENCE_ENDS)


def generate(
    model: Runnable[Any, Any],
    question: str,
    today: date,
    retrieval: Retrieval,
    retrying: Retrying | None = None,
) -> Answer:
    """The answer of ``model`` (a ``recommender``) to ``question`` asked on
    ``today``, from the events of ``retrieval``."""
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
