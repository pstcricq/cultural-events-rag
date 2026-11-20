"""The models every step works with: the agendas the events come from, their
raw events, and the event of the common format both sources are turned into."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class Agenda:
    """An Open Agenda agenda: its uid in the APIs and its title."""

    uid: int
    title: str


# The raw events of each agenda, as the API returns them, by agenda uid.
RawEvents = dict[int, list[dict[str, Any]]]


class Timing(BaseModel):
    begin: AwareDatetime
    end: AwareDatetime


class Location(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    address: str | None = None
    district: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class Event(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    uid: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    long_description: str = ""
    conditions: str | None = None
    # Free for everyone, paid, or unknown, read from the conditions.
    is_free: bool | None = None
    keywords: list[str] = Field(default_factory=list)
    timings: list[Timing] = Field(min_length=1)
    location: Location
    age_min: int | None = None
    age_max: int | None = None
    status: str
    registration: list[str] = Field(default_factory=list)
    url: str | None = None
    agenda_uid: int
    agenda_title: str
    updated_at: AwareDatetime | None = None

    @property
    def first_begin(self) -> datetime:
        return min(t.begin for t in self.timings)

    @property
    def last_end(self) -> datetime:
        return max(t.end for t in self.timings)
