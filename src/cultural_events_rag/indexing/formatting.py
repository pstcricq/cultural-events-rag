"""The French text of the values of an event: days, times, slots or the range
of a long series, in Paris time; the place; the audience. Dates are absolute
("samedi 19 septembre 2026"), never relative."""

from datetime import date, datetime
from itertools import groupby

from cultural_events_rag.constants import MONTHS, TIMEZONE, WEEKDAYS
from cultural_events_rag.models import Location, Timing

MAX_LISTED_DAYS = 7  # beyond this, the dates are written as a range


def format_day(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}"


def format_time(moment: datetime) -> str:
    return f"{moment.hour}h{moment.minute:02d}"


_Slot = tuple[datetime, datetime]


def _days(timings: list[Timing]) -> list[tuple[date, list[_Slot]]]:
    """Return the slots in Paris time, sorted and grouped by day."""
    slots = sorted(
        (t.begin.astimezone(TIMEZONE), t.end.astimezone(TIMEZONE)) for t in timings
    )
    return [
        (day, list(day_slots))
        for day, day_slots in groupby(slots, key=lambda s: s[0].date())
    ]


def _day_part(day: date, slots: list[_Slot]) -> str:
    """Return one day and its slots: "samedi 19 septembre 2026, 10h30-12h00,
    14h15-15h45"."""
    return f"{format_day(day)}, " + ", ".join(
        f"{format_time(begin)}-{format_time(end)}" for begin, end in slots
    )


def _date_parts(timings: list[Timing]) -> tuple[list[str], bool]:
    """Return the dates in Paris time, one part per day or a single range for a
    long series, and whether it is a range."""
    days = _days(timings)
    if len(days) > MAX_LISTED_DAYS:
        first, last = days[0][0], days[-1][0]
        slot_count = sum(len(slots) for _, slots in days)
        return [
            f"du {format_day(first)} au {format_day(last)} ({slot_count} créneaux)"
        ], True
    return [_day_part(day, slots) for day, slots in days], False


def format_timings(timings: list[Timing]) -> str:
    """Return the date lines of the header: the slots grouped by day, or a
    range for a long series."""
    parts, is_range = _date_parts(timings)
    if is_range:
        return f"Dates : {parts[0]}"
    if len(parts) == 1:
        return f"Date : {parts[0]}"
    return "Dates :\n" + "\n".join(f"- {part}" for part in parts)


def format_dates(timings: list[Timing]) -> str:
    """Return the dates on one line: the days and their slots, or the range of
    a long series."""
    parts, _ = _date_parts(timings)
    return "; ".join(parts)


def format_location(location: Location) -> str | None:
    parts = [
        part for part in (location.name, location.address or location.city) if part
    ]
    if not parts:
        return None
    text = ", ".join(parts)
    return f"{text} (quartier {location.district})" if location.district else text


def format_age(age_min: int | None, age_max: int | None) -> str | None:
    """Return the audience of an event, or None when it says nothing (0-99 or
    unknown)."""
    low = age_min or 0
    high = age_max if age_max is not None and age_max < 99 else None
    if low and high is not None:
        return f"de {low} à {high} ans"
    if low:
        return f"à partir de {low} ans"
    if high is not None:
        return f"jusqu'à {high} ans"
    return None
