"""What the command prints: an empty question refused."""

import pytest

from cultural_events_rag.cli import main


@pytest.mark.parametrize("command", ["analyze"])
def test_an_empty_question_is_refused_before_any_call(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_:
        main([command, " "])

    assert exit_.value.code == 2
    assert 'argument question: empty: with make, Q="..."' in capsys.readouterr().err
