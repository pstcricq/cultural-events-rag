"""Tests of the settings: environment, then .env, no defaults, empty means
unset, secrets masked."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cultural_events_rag.settings import Settings, get_settings
from tests import ROOT

# The variables only compose reads, never the application.
COMPOSE_ONLY = {
    "API_ELASTICSEARCH_URL",
    "ELASTIC_VERSION",
    "APP_IMAGE",
    "APP_TAG",
    "KIBANA_PASSWORD",
}


def _env_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_without_env_file_nor_variable_nothing_is_set(tmp_path: Path) -> None:
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert all(value is None for value in settings.model_dump().values())


def test_a_key_is_read_from_the_env_file(tmp_path: Path) -> None:
    settings = Settings(_env_file=_env_file(tmp_path, "MISTRAL_API_KEY=from-file\n"))
    assert settings.mistral_api_key is not None
    assert settings.mistral_api_key.get_secret_value() == "from-file"


def test_the_environment_wins_over_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "from-environment")
    settings = Settings(_env_file=_env_file(tmp_path, "MISTRAL_API_KEY=from-file\n"))
    assert settings.mistral_api_key is not None
    assert settings.mistral_api_key.get_secret_value() == "from-environment"


def test_an_empty_variable_is_unset(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=_env_file(tmp_path, "MISTRAL_API_KEY=\nMAX_EVENTS=\n")
    )
    assert settings.mistral_api_key is None
    assert settings.max_events is None


@pytest.mark.parametrize(("text", "value"), [("200", 200), ("all", "all")])
def test_the_cap_of_the_collection_is_a_number_or_all(
    text: str, value: int | str, tmp_path: Path
) -> None:
    settings = Settings(_env_file=_env_file(tmp_path, f"MAX_EVENTS={text}\n"))
    assert settings.max_events == value


@pytest.mark.parametrize("text", ["0", "some"])
def test_another_cap_is_refused(text: str, tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="max_events"):
        Settings(_env_file=_env_file(tmp_path, f"MAX_EVENTS={text}\n"))


def test_an_unknown_variable_is_ignored(tmp_path: Path) -> None:
    Settings(_env_file=_env_file(tmp_path, "SOMETHING_ELSE=1\n"))


def test_a_key_never_shows_in_a_repr(tmp_path: Path) -> None:
    settings = Settings(_env_file=_env_file(tmp_path, "OPENAGENDA_API_KEY=secret\n"))
    assert "secret" not in repr(settings)
    assert "secret" not in str(settings.model_dump())


def test_the_settings_are_read_once() -> None:
    assert get_settings() is get_settings()


def test_the_example_lists_the_same_variables_as_the_settings() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    variables = {
        line.split("=", 1)[0].lstrip("# ").strip()
        for line in example.splitlines()
        if "=" in line
    }
    assert variables == {name.upper() for name in Settings.model_fields} | COMPOSE_ONLY
