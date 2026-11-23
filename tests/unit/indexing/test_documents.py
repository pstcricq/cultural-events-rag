"""Tests of the documents: the header text, the optional lines, the metadata,
and one document per chunk."""

import json

from cultural_events_rag.indexing.chunking import make_splitter
from cultural_events_rag.indexing.documents import (
    event_header,
    event_metadata,
    event_text,
    event_to_documents,
    events_to_documents,
)
from cultural_events_rag.models import Event, Timing

# --- Text --------------------------------------------------------------------


def test_event_text_layout(event: Event) -> None:
    assert event_text(event) == (
        'Titre : Visite guidée "Les peintres caravagesques en LSF"\n'
        "Résumé : Visite guidée thématique des collections en français.\n"
        "Date : dimanche 21 juin 2026, 14h30-15h30\n"
        "Lieu : Musée des Augustins, 21 rue de Metz 31000 Toulouse"
        " (quartier Capitole / Arnaud Bernard / Carmes)\n"
        "Tarif : non précisé\n"
        "Mots-clés : visite, peinture\n"
        "Proposé par : Musée des Augustins\n"
        "\n"
        "Suivez les guides du musée.\n"
        "Découvrez les collections !"
    )


def test_paid_event_says_so(event: Event) -> None:
    paid = event.model_copy(
        update={"conditions": "Tarif unique : 6€", "is_free": False}
    )

    assert "Tarif : payant\nConditions : Tarif unique : 6€" in event_text(paid)


def test_optional_lines_only_when_informative(event: Event) -> None:
    text = event_text(
        event.model_copy(
            update={
                "conditions": "Entrée libre",
                "is_free": True,
                "age_min": 6,
                "status": "Annulé",
            }
        )
    )

    assert "Statut : Annulé" in text
    assert "Tarif : gratuit\nConditions : Entrée libre" in text
    assert "Public : à partir de 6 ans" in text
    assert "Statut" not in event_text(event)
    assert "Tarif : non précisé" in event_text(event)  # always written
    assert "Conditions" not in event_text(event)
    assert "Public" not in event_text(event)


def test_summary_skipped_when_repeated_in_description(event: Event) -> None:
    long_description = f"{event.description} Et bien plus encore."
    text = event_text(event.model_copy(update={"long_description": long_description}))

    assert "Résumé" not in text
    assert text.endswith(long_description)


# --- Metadata ----------------------------------------------------------------


def test_event_metadata(event: Event) -> None:
    metadata = event_metadata(event)

    assert metadata["uid"] == "4154446"
    assert metadata["first_begin"] == "2026-06-21T12:30:00+00:00"
    assert metadata["timings"] == [
        ["2026-06-21T12:30:00+00:00", "2026-06-21T13:30:00+00:00"]
    ]
    assert metadata["district"] == "Capitole / Arnaud Bernard / Carmes"
    assert metadata["is_free"] is None  # no conditions in the fixture
    json.dumps(metadata)  # serializable, to be stored in the index


def test_metadata_dates_normalized_to_utc(event: Event) -> None:
    paris_timing = Timing.model_validate(
        {"begin": "2026-06-21T14:30:00+02:00", "end": "2026-06-21T15:30:00+02:00"}
    )
    metadata = event_metadata(event.model_copy(update={"timings": [paris_timing]}))

    assert metadata["first_begin"] == "2026-06-21T12:30:00+00:00"


# --- Documents ---------------------------------------------------------------


def split_on_pipes(text: str) -> list[str]:
    """A fake splitter: the chunks are separated by pipes."""
    return [piece for piece in text.split("|") if piece]


def test_single_chunk_document(event: Event) -> None:
    [document] = event_to_documents(event, split_on_pipes)

    assert document.id == "4154446-0"
    assert document.page_content == event_text(event)
    assert document.metadata == event_metadata(event) | {
        "event_text": event_text(event),
        "chunk_index": 0,
        "chunk_count": 1,
    }


def test_empty_description_gives_the_header_only(event: Event) -> None:
    event = event.model_copy(update={"long_description": ""})

    [document] = event_to_documents(event, split_on_pipes)

    assert document.page_content == event_header(event)


def test_one_document_per_chunk_with_header_repeated(event: Event) -> None:
    event = event.model_copy(
        update={"long_description": "Partie 1.|Partie 2.|Partie 3."}
    )
    header = event_header(event)

    documents = event_to_documents(event, split_on_pipes)

    assert [d.id for d in documents] == ["4154446-0", "4154446-1", "4154446-2"]
    assert [d.page_content for d in documents] == [
        f"{header}\n\nPartie 1.",
        f"{header}\n\nPartie 2.",
        f"{header}\n\nPartie 3.",
    ]
    assert [d.metadata["chunk_index"] for d in documents] == [0, 1, 2]
    assert {d.metadata["chunk_count"] for d in documents} == {3}
    # The whole event in each chunk.
    assert {d.metadata["event_text"] for d in documents} == {event_text(event)}


def test_events_to_documents_flattens_all_events(event: Event) -> None:
    other = event.model_copy(update={"uid": "2", "long_description": "A.|B."})

    documents = events_to_documents([event, other], split_on_pipes)

    assert [d.id for d in documents] == ["4154446-0", "2-0", "2-1"]


def test_events_to_documents_with_the_real_splitter(event: Event) -> None:
    long_event = event.model_copy(update={"long_description": "Une phrase. " * 200})

    assert len(events_to_documents([long_event], make_splitter(1000, 150))) > 1


def test_single_chunk_equals_the_full_event_text(event: Event) -> None:
    [document] = event_to_documents(event, lambda text: [text])

    assert document.page_content == event_text(event)
