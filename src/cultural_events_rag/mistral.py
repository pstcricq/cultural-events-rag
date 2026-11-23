"""The Mistral models, built from the settings: the embedding model for the
documents and the questions, and the chat model for the answers.

Both are used through their LangChain interfaces, ``Embeddings`` and
``BaseChatModel``. ``MistralAIEmbeddings`` batches the texts up to 16k tokens
per request, counted with the Mistral tokenizer; its built-in retries are
turned off. A ``Pacer`` spaces the calls of a chat model to keep to the quota
of the plan."""

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

# The embedding model of the documents and the questions.
EMBEDDING_MODEL = "mistral-embed"
# The chat model that writes the answers.
LLM_MODEL = "ministral-14b-latest"
# The chat model that judges the answers.
JUDGE_MODEL = LLM_MODEL

# The tokenizer the embedding requests are counted with.
TOKENIZER_REPO = "mistralai/Mixtral-8x7B-v0.1"


def download_tokenizer() -> str:
    """Download the Mistral tokenizer into the Hugging Face cache and return
    its path."""
    return hf_hub_download(TOKENIZER_REPO, "tokenizer.json")


def mistral_tokenizer() -> Tokenizer:
    """Load the Mistral tokenizer from the Hugging Face cache."""
    try:
        return Tokenizer.from_pretrained(TOKENIZER_REPO)
    except OSError as exc:  # not downloaded, Hugging Face offline
        raise MissingModelError(
            f"no Mistral tokenizer ({TOKENIZER_REPO}) on this machine: run make models"
        ) from exc


def make_embeddings(settings: Settings) -> Embeddings:
    """Return the Mistral embedding model, ``EMBEDDING_MODEL``."""
    if not settings.mistral_api_key:
        raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
    return MistralAIEmbeddings(
        model=EMBEDDING_MODEL,
        mistral_api_key=settings.mistral_api_key,
        max_retries=None,
        tokenizer=mistral_tokenizer(),
    )


def requests_per_minute(settings: Settings) -> float:
    """Return the requests per minute the Mistral plan allows its chat models."""
    if settings.llm_requests_per_minute is None:
        raise MissingSettingError("LLM_REQUESTS_PER_MINUTE is not set: add it to .env")
    return settings.llm_requests_per_minute


class Pacer(BaseRateLimiter):
    """A rate limiter: at most ``per_minute`` requests a minute, each one ``60
    / per_minute`` seconds after the previous, the first at once."""

    def __init__(
        self,
        per_minute: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = 60 / per_minute
        self.clock, self.sleep = clock, sleep
        self.next = float("-inf")  # earliest time of the next request
        self.lock = threading.Lock()

    def _reserve(self, blocking: bool) -> float | None:
        """Take the next slot and return the wait before it; None when a wait
        is needed and ``blocking`` is false."""
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
    """Return the Mistral chat model ``LLM_MODEL``: temperature 0, a fixed
    seed, one attempt per call, its calls spaced by ``pacer`` (a new one by
    default; pass the same pacer to models sharing a quota)."""
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
