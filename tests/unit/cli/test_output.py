"""Tests of the command output: durations, aligned tables, yes or no questions,
and empty questions refused."""

import pytest

from cultural_events_rag.cli import main
from cultural_events_rag.cli.output import aligned, confirm, duration
from cultural_events_rag.settings import Settings

TABLE = [
    "| Configuration | Hit@5 |",
    "|:---:|---|",
    "| lexical | 0.93 |",
    "| hybrid + rerank | **1.00** |",
]


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [(40, "40 s"), (150, "2 min"), (9450, "2 h 38 min"), (7200, "2 h")],
)
def test_a_duration_as_a_person_reads_it(seconds: float, shown: str) -> None:
    assert duration(seconds) == shown


def test_a_table_aligned_for_the_terminal() -> None:
    assert aligned(TABLE) == [
        "Configuration    Hit@5",
        "----------------------",
        "lexical           0.93",
        "hybrid + rerank   1.00",
    ]
    assert aligned(TABLE, bold=True)[-1] == "hybrid + rerank  \033[1m 1.00\033[0m"


@pytest.mark.parametrize(
    ("typed", "yes"), [("y", True), ("oui", True), ("", False), ("n", False)]
)
def test_a_question_answered(
    typed: str, yes: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: typed)

    assert confirm("Run it?") is yes


def test_no_terminal_answers_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def closed(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", closed)

    assert not confirm("Run it?")


def test_an_evaluation_refused_runs_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prefix = "cultural_events_rag.cli.evaluate"
    settings = Settings(
        _env_file=None, rerank_available=True, llm_requests_per_minute=2
    )
    monkeypatch.setattr(f"{prefix}.get_settings", lambda: settings)
    monkeypatch.setattr(f"{prefix}._benchmark", lambda _: (None, None))
    monkeypatch.setattr("builtins.input", lambda _: "n")

    assert main(["evaluate", "generation"]) == 0
    assert main(["evaluate", "retrieval", "--no-rerank"]) == 0

    out = capsys.readouterr().out
    assert (
        "Estimated time: about 3 h 02 min: the answers 25 min, the judge 2 h 38 min, "
        "at 2 calls a minute." in out
    )
    assert "Estimated time: about 30 s, 3 configurations." in out
    assert out.count("Nothing run") == 2


@pytest.mark.parametrize(
    ("step", "values", "missing"),
    [
        ("retrieval", {}, "RERANK_AVAILABLE"),
        ("generation", {}, "RERANK_AVAILABLE"),
        ("generation", {"rerank_available": True}, "LLM_REQUESTS_PER_MINUTE"),
    ],
)
def test_an_evaluation_names_the_missing_setting(
    step: str,
    values: dict[str, object],
    missing: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(_env_file=None, **values)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "cultural_events_rag.cli.evaluate.get_settings", lambda: settings
    )

    assert main(["evaluate", step]) == 1

    assert f"{missing} is not set" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["analyze", "search", "ask"])
def test_an_empty_question_is_refused_before_any_call(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_:
        main([command, " "])

    assert exit_.value.code == 2
    assert 'argument question: empty: with make, Q="..."' in capsys.readouterr().err
