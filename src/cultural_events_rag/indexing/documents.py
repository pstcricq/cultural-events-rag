"""The documents of the index: the French text to embed and the metadata of
each event.

An event gives one document per chunk of its description, each starting with
the header of the event (title, dates, place, price). The metadata holds the
fields filtered on and the whole text of the event, the one given to the chat
model."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from langchain_core.documents import Document

from cultural_events_rag.indexing.chunking import TextSplitter
from cultural_events_rag.indexing.formatting import (
    format_age,
    format_location,
    format_timings,
)
from cultural_events_rag.models import Event

# Raised when the text or the metadata of the documents change: an index built
# before is then outdated.
DOCUMENT_FORMAT = 1
DEFAULT_STATUS = "Programmé"  # not written in the text
# The price line: free, paid or unknown.
PRICE_LABELS = {True: "gratuit", False: "payant", None: "non précisé"}


def event_header(event: Event) -> str:
    """Return the header of an event: its key facts, labelled, one per line."""
    summary = (
        None
        if event.long_description.startswith(event.description)
        else event.description
    )
    status = event.status if event.status != DEFAULT_STATUS else None
    fields = [
        ("Titre", event.title),
        ("Résumé", summary),
        (None, format_timings(event.timings)),
        ("Lieu", format_location(event.location)),
        ("Statut", status),
        ("Tarif", PRICE_LABELS[event.is_free]),
        ("Conditions", event.conditions),
        ("Public", format_age(event.age_min, event.age_max)),
        ("Mots-clés", ", ".join(event.keywords) or None),
        ("Proposé par", event.agenda_title),
    ]
    return "\n".join(
        value if label is None else f"{label} : {value}"
        for label, value in fields
        if value
    )


def _compose(header: str, body: str) -> str:
    return f"{header}\n\n{body}" if body else header


def event_text(event: Event) -> str:
    """Return the whole text of an event: its header and its whole description."""
    return _compose(event_header(event), event.long_description)


def _utc(moment: datetime) -> str:
    """Return ``moment`` in ISO 8601, in UTC."""
    return moment.astimezone(UTC).isoformat()


def event_metadata(event: Event) -> dict[str, Any]:
    """Return the metadata of an event, JSON-serializable."""
    return {
        "uid": event.uid,
        "title": event.title,
        "url": event.url,
        "agenda": event.agenda_title,
        "venue": event.location.name,
        "address": event.location.address,
        "district": event.location.district,
        "city": event.location.city,
        "latitude": event.location.latitude,
        "longitude": event.location.longitude,
        "first_begin": _utc(event.first_begin),
        "last_end": _utc(event.last_end),
        "timings": [[_utc(t.begin), _utc(t.end)] for t in event.timings],
        "status": event.status,
        "age_min": event.age_min,
        "age_max": event.age_max,
        "keywords": event.keywords,
        "is_free": event.is_free,
    }


def event_to_documents(event: Event, split: TextSplitter) -> list[Document]:
    """Return the documents of an event, one per chunk of its description (one
    for a short or empty description)."""
    header = event_header(event)
    pieces = split(event.long_description) or [""]
    metadata = event_metadata(event) | {"event_text": event_text(event)}
    return [
        Document(
            id=f"{event.uid}-{index}",
            page_content=_compose(header, piece),
            metadata=metadata | {"chunk_index": index, "chunk_count": len(pieces)},
        )
        for index, piece in enumerate(pieces)
    ]


def events_to_documents(events: Iterable[Event], split: TextSplitter) -> list[Document]:
    """Return the documents of every event, event after event."""
    return [
        document for event in events for document in event_to_documents(event, split)
    ]
