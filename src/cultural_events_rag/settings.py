"""The settings, read from the environment, then from ``.env``. None has a
default: an unset setting is None, and the code that needs it raises
``MissingSettingError``."""

from functools import lru_cache
from typing import Literal

from pydantic import PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from cultural_events_rag.paths import ENV_FILE


class Settings(BaseSettings):
    """One field per environment variable, named after it in lower case."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        # An empty variable is unset.
        env_ignore_empty=True,
    )

    # The API keys of Mistral and Open Agenda, kept out of repr and logs.
    openagenda_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None

    # The Elasticsearch URL, and the user and password the application signs in
    # with.
    elasticsearch_url: str | None = None
    elastic_user: str | None = None
    elastic_password: SecretStr | None = None
    # The alias the index of the events is served under; each build moves it to
    # a new index.
    elasticsearch_index: str | None = None

    # The number of events to collect, or all.
    max_events: PositiveInt | Literal["all"] | None = None

    # Whether this machine can run the reranker.
    rerank_available: bool | None = None

    # The requests per minute the Mistral plan allows its chat models.
    llm_requests_per_minute: float | None = None

    # The key of POST /rebuild, in the X-API-Key header; unset, the rebuild is
    # refused.
    admin_api_key: SecretStr | None = None

    # The URL of the API, for the web interface.
    api_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once per process."""
    return Settings()
