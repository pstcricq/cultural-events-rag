"""Tests of the Mistral models built from the settings, of the tokenizer, and
of the pacer."""

import asyncio
from typing import Any

import pytest
from langchain_mistralai import MistralAIEmbeddings
from pydantic import SecretStr
from tokenizers import Tokenizer, models

from cultural_events_rag.errors import MissingModelError, MissingSettingError
from cultural_events_rag.mistral import (
    Pacer,
    download_tokenizer,
    make_chat_model,
    make_embeddings,
    mistral_tokenizer,
)
from cultural_events_rag.settings import Settings

# A tokenizer of one word, made here: no file, no network.
TOKENIZER = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))


@pytest.fixture(autouse=True)
def offline_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return a local tokenizer: no Hugging Face in unit tests."""
    monkeypatch.setattr(
        "cultural_events_rag.mistral.Tokenizer.from_pretrained",
        lambda *_args: TOKENIZER,
    )


def test_a_missing_tokenizer_says_how_to_get_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def offline(repo: str) -> None:
        raise OSError("not in the cache, and offline")

    monkeypatch.setattr(
        "cultural_events_rag.mistral.Tokenizer.from_pretrained", offline
    )

    with pytest.raises(MissingModelError, match="run make models"):
        mistral_tokenizer()


def test_the_tokenizer_is_downloaded_from_its_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[Any, ...]] = []

    def download(*args: Any) -> str:
        asked.append(args)
        return "/cache/tokenizer.json"

    monkeypatch.setattr("cultural_events_rag.mistral.hf_hub_download", download)

    assert download_tokenizer() == "/cache/tokenizer.json"
    assert asked == [("mistralai/Mixtral-8x7B-v0.1", "tokenizer.json")]


@pytest.mark.parametrize("api_key", [None, SecretStr("")])
def test_missing_key_raises_a_clear_error(api_key: SecretStr | None) -> None:
    settings = Settings(_env_file=None, mistral_api_key=api_key)

    with pytest.raises(MissingSettingError, match="MISTRAL_API_KEY"):
        make_embeddings(settings)


def test_mistral_embeddings_configured_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        mistral_api_key=SecretStr("secret"),
    )

    embeddings = make_embeddings(settings)

    assert isinstance(embeddings, MistralAIEmbeddings)
    assert embeddings.model == "mistral-embed"
    assert embeddings.mistral_api_key.get_secret_value() == "secret"
    assert embeddings.max_retries is None  # retries are left to the caller
    assert embeddings.tokenizer is TOKENIZER


class Clock:
    """A clock that moves only when slept on."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_pacer_spaces_the_requests_the_first_at_once() -> None:
    clock = Clock()
    pacer = Pacer(2, clock=clock, sleep=clock.sleep)  # one every 30 s

    assert pacer.acquire()
    assert pacer.acquire()
    clock.now += 10  # a request that took 10 s
    assert pacer.acquire()

    assert clock.slept == [30.0, 20.0]


def test_the_pacer_without_blocking_refuses_to_wait() -> None:
    clock = Clock()
    pacer = Pacer(2, clock=clock, sleep=clock.sleep)

    assert pacer.acquire(blocking=False)
    assert not pacer.acquire(blocking=False)
    assert clock.slept == []


def test_the_pacer_waits_asynchronously(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    pacer = Pacer(60, clock=clock, sleep=clock.sleep)  # one a second
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("cultural_events_rag.mistral.asyncio.sleep", sleep)

    async def twice() -> list[bool]:
        return [await pacer.aacquire(), await pacer.aacquire()]

    assert asyncio.run(twice()) == [True, True]
    assert slept == [1.0]
    assert not asyncio.run(pacer.aacquire(blocking=False))


def test_the_chat_model_keeps_to_the_quota() -> None:
    settings = Settings(
        _env_file=None, mistral_api_key=SecretStr("secret"), llm_requests_per_minute=2
    )

    llm = make_chat_model(settings)

    assert isinstance(llm.rate_limiter, Pacer)
    assert llm.rate_limiter.interval == 30.0
    shared = Pacer(2)
    assert make_chat_model(settings, shared).rate_limiter is shared


def test_the_chat_model_needs_the_quota_of_the_plan() -> None:
    settings = Settings(_env_file=None, mistral_api_key=SecretStr("secret"))

    with pytest.raises(MissingSettingError, match="LLM_REQUESTS_PER_MINUTE"):
        make_chat_model(settings)
