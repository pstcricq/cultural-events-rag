"""The settings of the application: what an environment sets (its secrets,
where its services are, what its machine and its plans allow), read from the
environment, then from ``.env``, then from their defaults. A variable of the
environment wins over the same line of ``.env``.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from cultural_events_rag.paths import ENV_FILE


class Settings(BaseSettings):
    """One field per variable, named after it in lower case."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        # An empty variable, in .env or in the environment: unset.
        env_ignore_empty=True,
    )

    # The keys of the two APIs the assistant calls. SecretStr keeps them out of
    # every repr and log line.
    openagenda_api_key: SecretStr | None = None
    mistral_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """The settings, read once per process."""
    return Settings()
