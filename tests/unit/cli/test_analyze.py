"""cultural-events-rag analyze before any Elasticsearch: what to do when the
password is missing."""

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.settings import Settings


def test_analyze_names_the_missing_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(
        _env_file=None,
        elasticsearch_url="http://127.0.0.1:9200",
        elasticsearch_index="events",
        elastic_user="elastic",
    )
    monkeypatch.setattr(
        "cultural_events_rag.cli.analyze.get_settings", lambda: settings
    )

    assert main(["analyze", "Un concert ce soir ?"]) == 1

    assert "ELASTIC_PASSWORD is not set" in capsys.readouterr().err
