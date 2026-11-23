"""The models of the Mistral API the application calls, made from the
settings: the embedding model, that turns the documents (indexing) and the
questions (search) into vectors, and the chat model, that writes the answer.

Each model sits behind its LangChain interface (``Embeddings``,
``BaseChatModel``), so that another provider can take its place.
``MistralAIEmbeddings`` batches the texts, up to 16k tokens per request,
counted with the Mistral tokenizer of Hugging Face: downloaded once by ``make
models``, read offline then. Its own retries, a silent fixed 30 s wait, are
turned off: the build retries each batch itself, visibly, with an exponential
backoff.

The chat models of the free plan take 2 requests a minute: a ``Pacer`` spaces
the calls to keep to it, the first one at once, rather than letting Mistral
refuse them and retrying after longer and longer waits.
"""

import asyncio
import threading
import time
from collections.abc import Callable

from huggingface_hub import hf_hub_download
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import BaseRateLimiter
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from tokenizers import Tokenizer

from cultural_events_rag.errors import MissingModelError, MissingSettingError
from cultural_events_rag.settings import Settings

# The model that turns each document into the vector of the index.
EMBEDDING_MODEL = "mistral-embed"
# The model that writes the answer from the events found: the most capable of
# the free plan.
LLM_MODEL = "ministral-14b-latest"

# The tokenizer MistralAIEmbeddings counts the tokens with.
TOKENIZER_REPO = "mistralai/Mixtral-8x7B-v0.1"


def download_tokenizer() -> str:
    """Download the Mistral tokenizer into the cache of Hugging Face: its
    path."""
    return hf_hub_download(TOKENIZER_REPO, "tokenizer.json")


def mistral_tokenizer() -> Tokenizer:
    """The Mistral tokenizer, that MistralAIEmbeddings counts the tokens of
    the texts with, to keep each request under 16k tokens. Loaded here rather
    than by MistralAIEmbeddings, that falls back silently to counting
    characters when it is missing."""
    try:
        return Tokenizer.from_pretrained(TOKENIZER_REPO)
    except OSError as exc:  # not downloaded, and Hugging Face offline
        raise MissingModelError(
            f"no Mistral tokenizer ({TOKENIZER_REPO}) on this machine: run make models"
        ) from exc


def make_embeddings(settings: Settings) -> Embeddings:
    """The Mistral embedding model, EMBEDDING_MODEL."""
    if not settings.mistral_api_key:
        raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
    return MistralAIEmbeddings(
        model=EMBEDDING_MODEL,
        mistral_api_key=settings.mistral_api_key,
        max_retries=None,
        tokenizer=mistral_tokenizer(),
    )


def requests_per_minute(settings: Settings) -> float:
    """The calls a minute the Mistral plan allows its chat models."""
    if settings.llm_requests_per_minute is None:
        raise MissingSettingError("LLM_REQUESTS_PER_MINUTE is not set: add it to .env")
    return settings.llm_requests_per_minute


class Pacer(BaseRateLimiter):
    """At most ``per_minute`` requests a minute, evenly spaced: each one
    ``60 / per_minute`` seconds after the previous, the first at once."""

    def __init__(
        self,
        per_minute: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = 60 / per_minute
        self.clock, self.sleep = clock, sleep
        self.next = float("-inf")  # the earliest time of the next request
        self.lock = threading.Lock()

    def _reserve(self, blocking: bool) -> float | None:
        """The wait before the next request, its slot taken; None when it
        must wait and ``blocking`` is false."""
        with self.lock:
            now = self.clock()
            if now < self.next and not blocking:
                return None
            start = max(now, self.next)
            self.next = start + self.interval
            return start - now

    def acquire(self, *, blocking: bool = True) -> bool:
        wait = self._reserve(blocking)
        if wait is None:
            return False
        if wait > 0:
            self.sleep(wait)
        return True

    async def aacquire(self, *, blocking: bool = True) -> bool:
        wait = self._reserve(blocking)
        if wait is None:
            return False
        if wait > 0:
            await asyncio.sleep(wait)
        return True


def make_chat_model(settings: Settings, pacer: Pacer | None = None) -> BaseChatModel:
    """The Mistral chat model LLM_MODEL, as deterministic as it gets:
    temperature 0 and a fixed seed, its calls spaced by ``pacer`` (one of its
    own by default: share it between models that share a quota). One attempt
    per call: the caller retries, visibly."""
    if not settings.mistral_api_key:
        raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
    return ChatMistralAI(
        model=LLM_MODEL,
        api_key=settings.mistral_api_key,
        temperature=0,
        random_seed=0,
        max_retries=1,
        rate_limiter=pacer or Pacer(requests_per_minute(settings)),
    )
