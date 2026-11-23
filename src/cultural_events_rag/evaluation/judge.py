"""The judge of the answers, built on Ragas (the ``eval`` extra): three metrics
of the answers to the questions with relevant events.

- faithfulness: the share of the claims of the answer supported by the
  events given to the model;
- answer relevancy: how directly the answer addresses the question,
  compared by embeddings with questions generated from the answer;
- factual correctness: the claims of the answer and of the reference
  answer checked against each other (F1).

Ragas calls Mistral through its OpenAI-compatible API, its chat requests spaced
by the same ``Pacer`` as the assistant."""

import logging
import math
from collections.abc import Sequence
from typing import Any

import httpx
from instructor.core.exceptions import InstructorError
from openai import APIError, AsyncOpenAI, DefaultAsyncHttpxClient
from pydantic import ValidationError
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    FactualCorrectness,
    Faithfulness,
)

from cultural_events_rag.errors import MissingSettingError
from cultural_events_rag.evaluation.generation import (
    CORRECTNESS,
    FAITHFULNESS,
    RELEVANCY,
)
from cultural_events_rag.mistral import EMBEDDING_MODEL, JUDGE_MODEL, Pacer
from cultural_events_rag.settings import Settings

logger = logging.getLogger(__name__)

MISTRAL_API = "https://api.mistral.ai/v1"
# A refused request, or an output of the judge that does not parse.
JUDGE_FAILURES = (
    APIError,
    httpx.HTTPError,
    InstructorError,
    ValidationError,
    ValueError,
)


class RagasJudge:
    """The three Ragas metrics, their calls to the judge spaced by ``pacer``."""

    def __init__(self, settings: Settings, pacer: Pacer) -> None:
        if not settings.mistral_api_key:
            raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
        key = settings.mistral_api_key.get_secret_value()

        async def pace(request: object) -> None:
            await pacer.aacquire()

        paced = AsyncOpenAI(
            base_url=MISTRAL_API,
            api_key=key,
            max_retries=5,  # a 429 despite the pacing, retried with a backoff
            http_client=DefaultAsyncHttpxClient(event_hooks={"request": [pace]}),
        )
        # Mistral refuses a top_p below 1 at temperature 0; the default 1,024
        # tokens cut the claims of a long answer.
        llm = llm_factory(
            JUDGE_MODEL,
            client=paced,
            temperature=0,
            top_p=1,
            max_tokens=4096,
        )
        # The embeddings have their own quota: not paced.
        embeddings = OpenAIEmbeddings(
            client=AsyncOpenAI(base_url=MISTRAL_API, api_key=key),
            model=EMBEDDING_MODEL,
        )
        self.faithfulness = Faithfulness(llm=llm)
        # One generated question: at temperature 0, more would be identical.
        self.relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=1)
        self.correctness = FactualCorrectness(llm=llm)

    async def score(
        self, question: str, answer: str, contexts: Sequence[str], reference: str
    ) -> dict[str, float]:
        """Return the scores of an answer. A metric whose judge fails is logged
        and left out."""
        calls: dict[str, tuple[Any, dict[str, Any]]] = {
            FAITHFULNESS: (
                self.faithfulness,
                {
                    "user_input": question,
                    "response": answer,
                    "retrieved_contexts": list(contexts),
                },
            ),
            RELEVANCY: (self.relevancy, {"user_input": question, "response": answer}),
            CORRECTNESS: (
                self.correctness,
                {"response": answer, "reference": reference},
            ),
        }
        scores = {}
        for name, (metric, inputs) in calls.items():
            try:
                result = await metric.ascore(**inputs)
            except JUDGE_FAILURES as exc:
                logger.warning("%s failed on %r: %s", name, question, exc)
                continue
            value = result.value
            if isinstance(value, int | float) and not math.isnan(value):
                scores[name] = float(value)
        return scores
