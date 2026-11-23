"""Tests of the parsing of each source: HTML to text, the price, the fields of
each API, no personal data, invalid records counted."""

from datetime import UTC, datetime
from typing import Any

import pytest

from cultural_events_rag.collection.parsing import (
    PARSERS,
    html_to_text,
    is_free,
    parse_events,
    parse_openagenda_event,
    parse_opendatasoft_record,
)
from cultural_events_rag.collection.sources import OpenAgendaSource, OpenDataSoftSource
from cultural_events_rag.models import Agenda


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (None, ""),
        ("", ""),
        ("<p>Un <strong>concert</strong></p>", "Un concert"),
        ("<p>Ligne 1<br>Ligne 2</p><p>Ligne 3</p>", "Ligne 1\nLigne 2\nLigne 3"),
        ("Café &amp; concert&nbsp;!", "Café & concert !"),
        ("<p>retour\nbrut   et   espaces</p>", "retour brut et espaces"),
    ],
)
def test_html_to_text(html: str | None, expected: str) -> None:
    assert html_to_text(html) == expected


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        ("Gratuit", True),
        ("Entrée libre dans la limite des places disponibles", True),
        ("Accès libre et gratuit", True),
        ("Gratuit, retrait de billet à l'accueil du Quai", True),
        ("Tarif unique : 6€", False),
        ("De 10.29 € à 15.41 €", False),
        ("Tarifs : 60/50 €", False),
        ("Gratuit - 6 ans / 5€ tarif plein", False),  # free for some visitors only
        ("Entrée musée", False),
        ("Activité gratuite avec le billet d'entrée au musée", False),
        ("Comprise dans le billet d’entrée", False),
        ("Sur inscription", None),
        ("Participation libre", None),  # pay what you want: not free
        ("", None),
        (None, None),
    ],
)
def test_is_free(conditions: str | None, expected: bool | None) -> None:
    assert is_free(conditions) is expected


def test_parse_opendatasoft_record(ods_record: dict[str, Any], agenda: Agenda) -> None:
    event = parse_opendatasoft_record(ods_record, agenda)

    assert event.uid == "4154446"
    assert (
        event.long_description
        == "Suivez les guides du musée.\nDécouvrez les collections !"
    )
    assert event.keywords == ["visite", "peinture"]
    assert event.first_begin == datetime(2026, 6, 21, 12, 30, tzinfo=UTC)
    assert event.location.city == "Toulouse"
    assert event.location.latitude == pytest.approx(43.600942)
    assert event.status == "Programmé"
    assert event.registration == ["https://billetterie.example.com"]
    assert event.agenda_title == "Musée des Augustins"
    assert event.is_free is None  # no conditions


def test_personal_data_is_not_kept(ods_record: dict[str, Any], agenda: Agenda) -> None:
    dumped = parse_opendatasoft_record(ods_record, agenda).model_dump_json()

    assert "personne@example.com" not in dumped
    assert "Jane Doe" not in dumped


def test_parse_openagenda_event(
    openagenda_event: dict[str, Any], agenda: Agenda
) -> None:
    event = parse_openagenda_event(openagenda_event, agenda)

    assert event.uid == "56158955"
    assert event.long_description == "Soirée jazz.\nEntrée libre."
    assert len(event.timings) == 2
    assert event.last_end == datetime(2026, 11, 21, 21, 0, tzinfo=UTC)
    assert event.location.postal_code == "31000"
    assert (event.age_min, event.age_max) == (6, 99)
    assert event.status == "Complet"
    assert event.url == "https://openagenda.com/agendas/20289708/events/56158955"
    assert event.is_free is True  # "Gratuit"


def test_the_image_of_an_event_is_not_kept(
    ods_record: dict[str, Any], openagenda_event: dict[str, Any], agenda: Agenda
) -> None:
    # The image of an event is not kept.
    for event in (
        parse_opendatasoft_record(ods_record, agenda),
        parse_openagenda_event(openagenda_event, agenda),
    ):
        assert "img.openagenda.com" not in event.model_dump_json()


def test_parse_openagenda_multilingual_fields(
    openagenda_event: dict[str, Any], agenda: Agenda
) -> None:
    openagenda_event["title"] = {"en": "Jazz concert", "fr": "Concert de jazz"}
    openagenda_event["keywords"] = {"fr": ["jazz"]}

    event = parse_openagenda_event(openagenda_event, agenda)

    assert event.title == "Concert de jazz"
    assert event.keywords == ["jazz"]


def test_every_source_has_its_parser() -> None:
    assert set(PARSERS) == {OpenAgendaSource.name, OpenDataSoftSource.name}


@pytest.mark.parametrize(
    "change",
    [{"title_fr": None}, {"description_fr": "   "}, {"timings": "[]"}],
    ids=["no title", "blank description", "no timing"],
)
def test_a_raw_event_that_makes_no_valid_event_is_counted(
    ods_record: dict[str, Any], agenda: Agenda, change: dict[str, Any]
) -> None:
    items = [(agenda, ods_record), (agenda, ods_record | change)]

    events, invalid = parse_events(items, parse_opendatasoft_record)

    assert [event.uid for event in events] == ["4154446"]
    assert invalid == 1
