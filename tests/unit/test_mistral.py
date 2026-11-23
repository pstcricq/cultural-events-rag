"""The Mistral models made from the settings: the embedding model with the
tokenizer of Hugging Face, a missing tokenizer or key refused clearly."""

from typing import Any

import pytest
from langchain_mistralai import MistralAIEmbeddings
from pydantic import SecretStr
from tokenizers import Tokenizer, models

from cultural_events_rag.errors import MissingModelError, MissingSettingError
from cultural_events_rag.mistral import (
    download_tokenizer,
    make_embeddings,
    mistral_tokenizer,
)
from cultural_events_rag.settings import Settings

# A tokenizer of one word, made here: no file, no network.
TOKENIZER = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))


@pytest.fixture(autouse=True)
def offline_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never Hugging Face in unit tests: a tokenizer at hand."""
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
    assert embeddings.max_retries is None  # retries are handled (visibly) by the caller
    assert embeddings.tokenizer is TOKENIZER
