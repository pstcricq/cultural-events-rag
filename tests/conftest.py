"""For every test: no test reads the variables of the machine it runs on, each
sets its own. An agenda of the city."""

import pytest

from cultural_events_rag.models import Agenda
from cultural_events_rag.settings import Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def agenda() -> Agenda:
    return Agenda(20289708, "Musée des Augustins")
