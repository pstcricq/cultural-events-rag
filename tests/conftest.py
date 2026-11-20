"""For every test: no test reads the variables of the machine it runs on, each
sets its own."""

import pytest

from cultural_events_rag.settings import Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
