"""The LLM judge of the answers, built on Ragas (the eval extra): three
metrics of the answer itself, for the questions with relevant events.

- faithfulness: the share of the claims of the answer the events given to the
  LLM support (1: nothing invented);
- answer relevancy: how directly the answer addresses the question, the
  question written back from the answer and compared with it by embeddings;
- factual correctness: the claims of the answer and of the reference answer
  checked against each other (F1).

The context precision and context recall of Ragas are left out: they judge the
events given to the LLM, which the evaluation of the search measures against
human judgments. The out-of-scope questions too: answer relevancy rates a
refusal 0, and their abstention is measured exactly.

Ragas calls Mistral through its OpenAI-compatible API. The judge shares the
quota of the chat models with the LLM: its requests are spaced by the same
``Pacer``. The judge, ``JUDGE_MODEL``, is the model that wrote the answers:
a model tends to rate its own answers well, so the scores compare versions of
the assistant rather than tell an absolute quality.
"""

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
    """The three metrics of Ragas, their calls to the judge spaced by
    ``pacer``."""

    def __init__(self, settings: Settings, pacer: Pacer) -> None:
        if not settings.mistral_api_key:
            raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
        key = settings.mistral_api_key.get_secret_value()

        async def pace(request: object) -> None:
            await pacer.aacquire()

        paced = AsyncOpenAI(
            base_url=MISTRAL_API,
            api_key=key,
            max_retries=5,  # a 429 despite the pacing: retried, with a backoff
            http_client=DefaultAsyncHttpxClient(event_hooks={"request": [pace]}),
        )
        # Mistral refuses a top_p below 1 at temperature 0; 1,024 tokens, the
        # default, cut the claims of a long answer.
        llm = llm_factory(
            JUDGE_MODEL,
            client=paced,
            temperature=0,
            top_p=1,
            max_tokens=4096,
        )
        # The embeddings have a quota of their own, far larger: not paced.
        embeddings = OpenAIEmbeddings(
            client=AsyncOpenAI(base_url=MISTRAL_API, api_key=key),
            model=EMBEDDING_MODEL,
        )
        self.faithfulness = Faithfulness(llm=llm)
        # One question written back: at temperature 0, three would be the same.
        self.relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=1)
        self.correctness = FactualCorrectness(llm=llm)

    async def score(
        self, question: str, answer: str, contexts: Sequence[str], reference: str
    ) -> dict[str, float]:
        """The scores of an answer: a metric whose judge fails is left out,
        logged, so that one failure does not stop a run of hours."""
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
