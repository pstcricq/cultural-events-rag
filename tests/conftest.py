"""Fixtures of every test: an environment without the variables of the machine,
one raw event per source, and the event it makes."""

from typing import Any

import pytest

from cultural_events_rag.collection.parsing import parse_opendatasoft_record
from cultural_events_rag.models import Agenda, Event
from cultural_events_rag.settings import Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def agenda() -> Agenda:
    return Agenda(20289708, "Musée des Augustins")


@pytest.fixture
def ods_record() -> dict[str, Any]:
    """An OpenDataSoft record: JSON fields serialized as strings, HTML descriptions."""
    return {
        "uid": "4154446",
        "canonicalurl": "https://openagenda.com/musee-des-augustins-toulouse/events/visite",
        "title_fr": 'Visite guidée "Les peintres caravagesques en LSF"',
        "description_fr": "Visite guidée thématique des collections en français.",
        "longdescription_fr": (
            "<p>Suivez les guides du musée.<br>Découvrez les collections&nbsp;!</p>"
        ),
        "conditions_fr": None,
        "keywords_fr": ["visite", "peinture"],
        "updatedat": "2026-06-11T12:46:35.036000+00:00",
        "timings": '[{"begin": "2026-06-21T14:30:00+02:00", "end": "2026-06-21T15:30:00+02:00"}]',
        "location_coordinates": {"lon": 1.446343, "lat": 43.600942},
        "location_name": "Musée des Augustins",
        "location_address": "21 rue de Metz 31000 Toulouse",
        "location_district": "Capitole / Arnaud Bernard / Carmes",
        "location_postalcode": "31000",
        "location_city": "Toulouse",
        "status": '{"id": 1, "label": {"fr": "Programmé"}}',
        "age_min": None,
        "age_max": None,
        "originagenda_uid": "20289708",
        "contributor_email": "personne@example.com",
        "contributor_contactname": "Jane Doe",
        "registration": '[{"type": "link", "value": "https://billetterie.example.com"}]',
        "image": "https://img.openagenda.com/main/visite.base.image.jpg",
    }


@pytest.fixture
def openagenda_event() -> dict[str, Any]:
    """An event of the official API v2
    (``detailed=1&monolingual=fr&longDescriptionFormat=HTML``)."""
    return {
        "uid": 56158955,
        "title": "Concert de jazz",
        "description": "Un trio jazz au conservatoire.",
        "longDescription": "<p>Soirée <strong>jazz</strong>.</p><p>Entrée libre.</p>",
        "conditions": "Gratuit",
        "keywords": ["jazz", "concert"],
        "timings": [
            {"begin": "2026-11-20T20:00:00+0100", "end": "2026-11-20T22:00:00+0100"},
            {"begin": "2026-11-21T20:00:00+0100", "end": "2026-11-21T22:00:00+0100"},
        ],
        "location": {
            "name": "Conservatoire de Toulouse",
            "address": "17 rue Larrey",
            "city": "Toulouse",
            "postalCode": "31000",
            "latitude": 43.6045,
            "longitude": 1.4389,
        },
        "age": {"min": 6, "max": 99},
        "status": 5,
        "registration": [{"type": "email", "value": "contact@example.com"}],
        "image": {
            "base": "https://img.openagenda.com/main/",
            "filename": "abc.base.image.jpg",
        },
        "updatedAt": "2026-10-01T10:00:00.000Z",
    }


@pytest.fixture
def event(ods_record: dict[str, Any], agenda: Agenda) -> Event:
    """A cleaned event: one timing, Sunday 21 June 2026 14:30-15:30 Paris time."""
    return parse_opendatasoft_record(ods_record, agenda)
