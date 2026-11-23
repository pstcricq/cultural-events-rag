"""cultural-events-rag models, Hugging Face replaced: the tokenizer and the
reranker downloaded, no reranker when RERANK_AVAILABLE is false, nothing when
it is not set, a failed download reported."""

from pathlib import Path

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.settings import Settings


@pytest.fixture
def downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []
    tokenizer = tmp_path / "tokenizer" / "tokenizer.json"
    tokenizer.parent.mkdir()
    tokenizer.write_bytes(b"x" * 2_000_000)
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.safetensors").write_bytes(b"x" * 300_000_000)

    def download_tokenizer() -> str:
        asked.append("tokenizer")
        return str(tokenizer)

    def download_cross_encoder(name: str) -> str:
        asked.append(name)
        return str(model)

    prefix = "cultural_events_rag.cli.models"
    monkeypatch.setattr(f"{prefix}.download_tokenizer", download_tokenizer)
    monkeypatch.setattr(f"{prefix}.download_cross_encoder", download_cross_encoder)
    return asked


def _settings(monkeypatch: pytest.MonkeyPatch, **values: object) -> None:
    values = {"rerank_available": True, **values}
    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]
    monkeypatch.setattr("cultural_events_rag.cli.models.get_settings", lambda: settings)


def test_models_downloads_the_tokenizer_and_the_reranker(
    downloads: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _settings(monkeypatch)

    assert main(["models"]) == 0

    out = capsys.readouterr().out
    assert downloads == ["tokenizer", "BAAI/bge-reranker-v2-m3"]
    assert "Tokenizer: mistralai/Mixtral-8x7B-v0.1, 2 MB -> " in out
    assert "Reranker: BAAI/bge-reranker-v2-m3, 0.3 GB -> " in out


def test_models_without_reranker(
    downloads: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _settings(monkeypatch, rerank_available=False)

    assert main(["models"]) == 0

    assert downloads == ["tokenizer"]
    assert "Reranker: none, RERANK_AVAILABLE is false" in capsys.readouterr().out


def test_models_refuses_an_unset_rerank_available(
    downloads: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _settings(monkeypatch, rerank_available=None)

    assert main(["models"]) == 1

    assert downloads == []
    assert "RERANK_AVAILABLE is not set" in capsys.readouterr().err


def test_models_reports_a_failed_download(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _settings(monkeypatch)

    def offline() -> str:
        raise OSError("no network")

    monkeypatch.setattr("cultural_events_rag.cli.models.download_tokenizer", offline)

    assert main(["models"]) == 1

    assert "FAIL download from Hugging Face: no network" in capsys.readouterr().err
