"""The settings of the application: what an environment sets (its secrets,
where its services are, what its machine and its plans allow), read from the
environment, then from ``.env``, unset otherwise: none has a default here,
``.env.example`` gives each one its value. A variable of the environment wins
over the same line of ``.env``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PositiveInt, SecretStr
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

    # The search engine holding the index, and the user the application signs
    # in as, with its password: each environment chooses them (the port
    # compose publishes and elastic, the built-in superuser of compose.yaml, on
    # a laptop; a role-limited user elsewhere).
    elasticsearch_url: str | None = None
    elastic_user: str | None = None
    elastic_password: SecretStr | None = None
    # The alias the index of the events is served under: each build writes a
    # new index and moves the alias onto it.
    elasticsearch_index: str | None = None

    # How many events `fetch` collects from the agendas of CITY: a number (a
    # sample while developing), or all. No default: the collection refuses to
    # run without one, a forgotten cap is not a choice.
    max_events: PositiveInt | Literal["all"] | None = None


@lru_cache
def get_settings() -> Settings:
    """The settings, read once per process."""
    return Settings()
