"""The models every step works with: the agendas the events come from, and
their raw events."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Agenda:
    """An Open Agenda agenda: its uid in the APIs and its title."""

    uid: int
    title: str


# The raw events of each agenda, as the API returns them, by agenda uid.
RawEvents = dict[int, list[dict[str, Any]]]
