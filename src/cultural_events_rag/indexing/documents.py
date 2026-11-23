"""Turn events into the documents stored in the index: French text to embed, plus metadata.

An event gives one document per description chunk. Each starts with the event header (title,
dates, place, price...), so its vector stays tied to the event. Metadata is used for filtering
(dates, area, audience) and citing sources; it holds the whole text of the event too, header and
whole description, the one the LLM reads: the best chunk of a long description can leave out
its sessions or its prices.

The values are written in French by ``formatting``.
"""

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

# Bumped when the text or the metadata of the documents change: an index built
# before is then reported outdated, and built again.
DOCUMENT_FORMAT = 1
DEFAULT_STATUS = "Programmé"  # not worth mentioning in the text
# The price, always written: free ("Entrée libre" reads as free), paid, or
# unknown, which a free question keeps too.
PRICE_LABELS = {True: "gratuit", False: "payant", None: "non précisé"}


def event_header(event: Event) -> str:
    """Labelled key facts (title, dates, place, price...), repeated at the top of every chunk."""
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
    """Full French text of an event (header + whole description), as given to the LLM."""
    return _compose(event_header(event), event.long_description)


def _utc(moment: datetime) -> str:
    """ISO 8601 in UTC: one offset for every event, so dates compare correctly."""
    return moment.astimezone(UTC).isoformat()


def event_metadata(event: Event) -> dict[str, Any]:
    """JSON-serializable metadata, used for filtering (dates, area, audience) and citing sources."""
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
    """One document per description chunk (a single one for short or empty descriptions)."""
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
    """The documents of every event, event after event."""
    return [
        document for event in events for document in event_to_documents(event, split)
    ]
