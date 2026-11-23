"""cultural-events-rag models, Hugging Face replaced: the tokenizer
downloaded, a failed download reported."""

from pathlib import Path

import pytest

from cultural_events_rag.cli import main


@pytest.fixture
def downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []
    tokenizer = tmp_path / "tokenizer" / "tokenizer.json"
    tokenizer.parent.mkdir()
    tokenizer.write_bytes(b"x" * 2_000_000)

    def download_tokenizer() -> str:
        asked.append("tokenizer")
        return str(tokenizer)

    prefix = "cultural_events_rag.cli.models"
    monkeypatch.setattr(f"{prefix}.download_tokenizer", download_tokenizer)
    return asked


def test_models_downloads_the_tokenizer(
    downloads: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["models"]) == 0

    assert downloads == ["tokenizer"]
    assert "Tokenizer: mistralai/Mixtral-8x7B-v0.1, 2 MB -> " in capsys.readouterr().out


def test_models_reports_a_failed_download(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def offline() -> str:
        raise OSError("no network")

    monkeypatch.setattr("cultural_events_rag.cli.models.download_tokenizer", offline)

    assert main(["models"]) == 1

    assert "FAIL download from Hugging Face: no network" in capsys.readouterr().err
