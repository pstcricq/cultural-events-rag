"""Tests of ``config show``: one line per setting, secrets masked."""

from pathlib import Path

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.settings import Settings


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAGENDA_API_KEY=secret\n", encoding="utf-8")
    loaded = Settings(_env_file=env_file)
    monkeypatch.setattr("cultural_events_rag.cli.config.get_settings", lambda: loaded)
    return loaded


def test_show_prints_one_line_per_setting(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config", "show"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == len(Settings.model_fields)
    assert out[0].split() == ["OPENAGENDA_API_KEY", "set"]
    assert out[1].split() == ["MISTRAL_API_KEY", "not", "set"]


def test_show_never_prints_a_secret(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["config", "show"])
    assert "secret" not in capsys.readouterr().out


def test_config_names_its_step(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as refused:
        main(["config"])
    assert refused.value.code == 2
    assert "show" in capsys.readouterr().err
