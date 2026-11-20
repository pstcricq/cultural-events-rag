"""The settings come from the environment, then from .env, then from their
defaults, an empty one is unset, and a key never shows in a repr."""

from pathlib import Path

import pytest

from cultural_events_rag.settings import Settings, get_settings
from tests import ROOT


def _env_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_without_env_file_nor_variable_no_key_is_set(tmp_path: Path) -> None:
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert settings.openagenda_api_key is None
    assert settings.mistral_api_key is None


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
    settings = Settings(_env_file=_env_file(tmp_path, "MISTRAL_API_KEY=\n"))
    assert settings.mistral_api_key is None


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
    assert variables == {name.upper() for name in Settings.model_fields}
