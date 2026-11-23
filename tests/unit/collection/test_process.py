"""Tests of the processing: parsing, cleaning and merging chained, every drop
counted."""

from datetime import UTC, datetime
from typing import Any

from cultural_events_rag.collection.process import process_events
from cultural_events_rag.models import Agenda, RawEvents

SINCE = datetime(2025, 10, 15, tzinfo=UTC)
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def test_each_source_is_read_by_its_own_parser(
    ods_record: dict[str, Any], openagenda_event: dict[str, Any], agenda: Agenda
) -> None:
    opendatasoft = process_events(
        {agenda.uid: [ods_record]}, "opendatasoft", [agenda], "Toulouse", SINCE, NOW
    )
    openagenda = process_events(
        {agenda.uid: [openagenda_event]}, "openagenda", [agenda], "Toulouse", SINCE, NOW
    )

    assert [e.uid for e in opendatasoft.events] == ["4154446"]
    assert [e.uid for e in openagenda.events] == ["56158955"]


def test_the_events_are_cleaned_and_their_drops_counted(
    ods_record: dict[str, Any], agenda: Agenda
) -> None:
    raw: RawEvents = {
        agenda.uid: [
            ods_record,
            ods_record,  # the same event twice
            ods_record | {"uid": "2", "location_city": "Blagnac"},
            ods_record | {"uid": "3", "title_fr": None},
        ]
    }

    report = process_events(raw, "opendatasoft", [agenda], "Toulouse", SINCE, NOW)

    assert [e.uid for e in report.events] == ["4154446"]
    assert report.dropped == {"duplicate": 1, "out_of_area": 1, "invalid": 1}


def test_the_sessions_of_one_activity_are_merged_and_counted(
    ods_record: dict[str, Any], agenda: Agenda
) -> None:
    raw: RawEvents = {agenda.uid: [ods_record | {"uid": str(i)} for i in range(4)]}

    report = process_events(raw, "opendatasoft", [agenda], "Toulouse", SINCE, NOW)

    assert len(report.events) == 1
    assert report.merged == 3


def test_an_agenda_left_out_since_the_download_is_skipped(
    ods_record: dict[str, Any], agenda: Agenda
) -> None:
    raw: RawEvents = {agenda.uid: [ods_record], 1: [ods_record | {"uid": "9"}]}

    report = process_events(raw, "opendatasoft", [agenda], "Toulouse", SINCE, NOW)

    assert [e.uid for e in report.events] == ["4154446"]
