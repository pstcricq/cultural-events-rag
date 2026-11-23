"""The parsing of the raw events of each source into events of the common
format: fields mapped, HTML turned into text, price read from the conditions. A
record that makes no valid event is counted and dropped."""

import json
import logging
import re
import unicodedata
from collections.abc import Callable, Iterable
from html.parser import HTMLParser
from typing import Any

from pydantic import ValidationError

from cultural_events_rag.collection.sources import OpenAgendaSource, OpenDataSoftSource
from cultural_events_rag.models import Agenda, Event

logger = logging.getLogger(__name__)

Parser = Callable[[dict[str, Any], Agenda], Event]

# The Open Agenda status codes, with their French labels.
STATUS_LABELS = {
    1: "Programmé",
    2: "Reprogrammé",
    3: "Déplacé en ligne",
    4: "Reporté",
    5: "Complet",
    6: "Annulé",
}

_HEADINGS = {f"h{n}" for n in range(1, 7)}
_BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "tr"} | _HEADINGS

_PRICE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:€|euros?\b)")
_FREE = ("gratuit", "entree libre", "acces libre")
# a paid admission ticket is needed, even for a free activity
_TICKET = (
    "billet d'entree",
    "entree musee",
    "entree du musee",
    "compris dans le billet",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        # In HTML a raw newline is whitespace: only block tags break lines.
        self.parts.append(" ".join(data.splitlines()))


def is_free(conditions: str | None) -> bool | None:
    """Return whether an event is free, read from its conditions ("Gratuit",
    "Tarif : 6€"...).

    True: free for everyone. False: paid, at least for some visitors ("Gratuit
    - 6 ans / 5€") or with a museum ticket. None: unknown (no conditions, "Sur
    inscription", "Participation libre")."""
    if not conditions:
        return None
    decomposed = unicodedata.normalize("NFKD", conditions.casefold().replace("’", "'"))
    text = "".join(c for c in decomposed if not unicodedata.combining(c))
    if _PRICE.search(text) or any(marker in text for marker in _TICKET):
        return False
    if any(marker in text for marker in _FREE):
        return True
    return None


def html_to_text(value: str | None) -> str:
    """Convert HTML to plain text: tags stripped, entities decoded, whitespace
    normalized."""
    if not value:
        return ""
    extractor = _TextExtractor()
    extractor.feed(value)
    extractor.close()
    lines = (" ".join(line.split()) for line in "".join(extractor.parts).splitlines())
    return "\n".join(line for line in lines if line)


def _fr(value: Any) -> Any:
    """Return the French value of a multilingual field (``{"fr": ...}``), or
    the value as is."""
    if isinstance(value, dict):
        return value.get("fr") or next(iter(value.values()), None)
    return value


def _json_field(value: Any) -> Any:
    """Return a field OpenDataSoft serializes as a JSON string, decoded."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _status_label(value: Any) -> str:
    status = _json_field(value)
    status_id = status.get("id") if isinstance(status, dict) else status
    return STATUS_LABELS.get(status_id or 1, "Programmé")


def _registration(value: Any) -> list[str]:
    return [
        str(item["value"]) for item in _json_field(value) or [] if item.get("value")
    ]


def parse_openagenda_event(data: dict[str, Any], agenda: Agenda) -> Event:
    """Convert an event of the official Open Agenda API (v2)."""
    location = data.get("location") or {}
    age = data.get("age") or {}
    uid = str(data["uid"])
    conditions = html_to_text(_fr(data.get("conditions"))) or None
    payload = {
        "uid": uid,
        "title": html_to_text(_fr(data.get("title"))),
        "description": html_to_text(_fr(data.get("description"))),
        "long_description": html_to_text(_fr(data.get("longDescription"))),
        "conditions": conditions,
        "is_free": is_free(conditions),
        "keywords": _fr(data.get("keywords")) or [],
        "timings": data.get("timings") or [],
        "location": {
            "name": location.get("name"),
            "address": location.get("address"),
            "district": location.get("district"),
            "city": location.get("city"),
            "postal_code": location.get("postalCode"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
        "age_min": age.get("min"),
        "age_max": age.get("max"),
        "status": _status_label(data.get("status")),
        "registration": _registration(data.get("registration")),
        "url": data.get("canonicalUrl")
        or f"https://openagenda.com/agendas/{agenda.uid}/events/{uid}",
        "agenda_uid": agenda.uid,
        "agenda_title": agenda.title,
        "updated_at": data.get("updatedAt"),
    }
    return Event.model_validate(payload)


def parse_opendatasoft_record(data: dict[str, Any], agenda: Agenda) -> Event:
    """Convert a record of the OpenDataSoft dataset
    ``evenements-publics-openagenda``. The personal data of the contributors
    (``contributor_*`` fields) is not kept."""
    coordinates = data.get("location_coordinates") or {}
    conditions = html_to_text(data.get("conditions_fr")) or None
    payload = {
        "uid": str(data["uid"]),
        "title": html_to_text(data.get("title_fr")),
        "description": html_to_text(data.get("description_fr")),
        "long_description": html_to_text(data.get("longdescription_fr")),
        "conditions": conditions,
        "is_free": is_free(conditions),
        "keywords": data.get("keywords_fr") or [],
        "timings": _json_field(data.get("timings")) or [],
        "location": {
            "name": data.get("location_name"),
            "address": data.get("location_address"),
            "district": data.get("location_district"),
            "city": data.get("location_city"),
            "postal_code": data.get("location_postalcode"),
            "latitude": coordinates.get("lat"),
            "longitude": coordinates.get("lon"),
        },
        "age_min": data.get("age_min"),
        "age_max": data.get("age_max"),
        "status": _status_label(data.get("status")),
        "registration": _registration(data.get("registration")),
        "url": data.get("canonicalurl"),
        "agenda_uid": agenda.uid,
        "agenda_title": agenda.title,
        "updated_at": data.get("updatedat"),
    }
    return Event.model_validate(payload)


# The parser of each source, by source name.
PARSERS: dict[str, Parser] = {
    OpenAgendaSource.name: parse_openagenda_event,
    OpenDataSoftSource.name: parse_opendatasoft_record,
}


def parse_events(
    items: Iterable[tuple[Agenda, dict[str, Any]]], parse: Parser
) -> tuple[list[Event], int]:
    """Parse the raw events of each agenda with ``parse``; return the events
    and the number of raw events that make no valid event."""
    events: list[Event] = []
    invalid = 0
    for agenda, data in items:
        try:
            events.append(parse(data, agenda))
        except (ValidationError, KeyError, ValueError) as exc:
            logger.debug("Event %s invalid: %s", data.get("uid"), exc)
            invalid += 1
    return events, invalid
