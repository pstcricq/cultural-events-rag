"""cultural-events-rag search before any Elasticsearch: what to do when a
setting is missing."""

import pytest
from pydantic import SecretStr

from cultural_events_rag.cli import main
from cultural_events_rag.settings import Settings


@pytest.mark.parametrize(
    ("values", "args", "missing"),
    [
        ({}, ["--mode", "lexical"], "ELASTIC_PASSWORD"),
        (
            {"elastic_password": SecretStr("password")},
            ["--mode", "hybrid"],
            "MISTRAL_API_KEY",
        ),
    ],
)
def test_search_names_the_missing_setting(
    values: dict[str, SecretStr],
    args: list[str],
    missing: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        _env_file=None,
        elasticsearch_url="http://127.0.0.1:9200",
        elasticsearch_index="events",
        elastic_user="elastic",
        **values,  # type: ignore[arg-type]
    )
    monkeypatch.setattr("cultural_events_rag.cli.search.get_settings", lambda: settings)

    assert main(["search", "Un concert ce soir ?", *args]) == 1

    assert f"{missing} is not set" in capsys.readouterr().err


def test_search_needs_a_mode(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["search", "Un concert ce soir ?"])

    assert "the following arguments are required: --mode" in capsys.readouterr().err
