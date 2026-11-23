"""Tests of the ``fetch`` command against a fake OpenDataSoft: the raw file,
the output, the exit code, and the required cap."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.constants import CULTURAL_AGENDAS
from cultural_events_rag.settings import Settings


def _opendatasoft(request: httpx.Request) -> httpx.Response:
    """Two upcoming events per agenda, no past one."""
    where = request.url.params["where"]
    if "lastdate_end >= now()" not in where:
        return httpx.Response(200, json={"results": []})
    agenda = where.split('originagenda_uid="')[1].split('"')[0]
    results: list[dict[str, Any]] = [{"uid": f"{agenda}-{i}"} for i in range(2)]
    return httpx.Response(200, json={"results": results})


@pytest.fixture
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """No key, so OpenDataSoft; every event; the raw file written in tmp_path."""
    settings = Settings(_env_file=None, max_events="all")
    monkeypatch.setattr("cultural_events_rag.cli.fetch.get_settings", lambda: settings)
    monkeypatch.setattr("cultural_events_rag.cli.fetch.RAW_DIR", tmp_path)
    return tmp_path


def _serve(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("cultural_events_rag.cli.fetch._client", lambda: client)


def test_fetch_writes_the_raw_events_of_every_agenda(
    raw_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _serve(monkeypatch, _opendatasoft)

    assert main(["fetch"]) == 0

    raw = json.loads((raw_dir / "opendatasoft.json").read_text(encoding="utf-8"))
    assert list(raw) == [str(agenda.uid) for agenda in CULTURAL_AGENDAS]
    assert all(len(events) == 2 for events in raw.values())
    out = capsys.readouterr().out
    assert out.startswith("Source: opendatasoft, city: Toulouse")
    assert f"{2 * len(CULTURAL_AGENDAS)} raw events -> " in out


def test_fetch_fails_on_a_source_error(
    raw_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _serve(monkeypatch, lambda request: httpx.Response(400, text="bad request"))

    assert main(["fetch"]) == 1

    assert "FAIL HTTP 400" in capsys.readouterr().err
    assert not list(raw_dir.iterdir())


def test_fetch_needs_a_cap(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(_env_file=None)
    monkeypatch.setattr("cultural_events_rag.cli.fetch.get_settings", lambda: settings)

    assert main(["fetch"]) == 1

    assert "MAX_EVENTS is not set: add it to .env, a number or all" in (
        capsys.readouterr().err
    )


def test_fetch_takes_a_cap_for_one_run(
    raw_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _serve(monkeypatch, _opendatasoft)

    assert main(["fetch", "--max-events", "11"]) == 0
    assert ", cap: 11\n" in capsys.readouterr().out

    _serve(monkeypatch, _opendatasoft)  # a client of its own: the first is closed
    assert main(["fetch", "--max-events", "all"]) == 0
    assert ", cap: all\n" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["0", "-3", "some"])
def test_a_cap_is_a_number_above_0_or_all(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(["fetch", "--max-events", value])

    assert "a number above 0, or all" in capsys.readouterr().err
