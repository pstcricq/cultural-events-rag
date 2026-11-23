"""The analysis of a question: its constraints (period, free entry, place)
turned into search filters by French rules, without a model. The known places
are the districts and venues of the index."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from elasticsearch import Elasticsearch

from cultural_events_rag.constants import (
    CITY,
    DEPARTMENT,
    HOLIDAYS,
    MONTHS,
    SEASONS,
    WEEKDAYS,
    DayMonth,
)
from cultural_events_rag.retrieval.filters import SearchFilters

# --- Periods -----------------------------------------------------------------

Period = tuple[date | None, date | None]


def _fold(question: str) -> str:
    """Return ``text`` in lower case, without accents, with one spelling of
    "weekend" and of the apostrophe."""
    text = unicodedata.normalize("NFKD", question.casefold().replace("’", "'"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"week[- ]?end", "weekend", text)
    return " ".join(text.split())


# The calendar, folded ("fevrier", "noel").
_MONTHS = {_fold(name): number for number, name in enumerate(MONTHS, 1)}
_WEEKDAYS = {_fold(name): number for number, name in enumerate(WEEKDAYS)}
_SEASONS = {_fold(name): days for name, days in SEASONS.items()}
# Longest name first: "vacances de noel" before "noel".
_HOLIDAYS = {
    _fold(name): HOLIDAYS[name] for name in sorted(HOLIDAYS, key=len, reverse=True)
}

_MONTH = "(" + "|".join(_MONTHS) + ")"
_DAY = r"(\d{1,2})(?:er)?"
_DATE = rf"{_DAY} {_MONTH}(?: (\d{{4}}))?"
_NUMERIC_DATE = r"\d{1,2}/\d{1,2}(?:/\d{4})?"
_PAST = re.compile(r"\b(?:hier|dernier|derniere|avait|etait|y a eu|a eu lieu|s'est)\b")


def _end_of_month(year: int, month: int) -> date:
    return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)


def _occurrence(
    start: DayMonth, end: DayMonth, today: date, past: bool
) -> tuple[date, date]:
    """Return the next occurrence of a period (the one under way from today),
    or the last one for the past."""
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        first = date(year, start[0], start[1])
        last = date(year + (end < start), end[0], end[1])  # over the new year
        candidates.append((first, last))
    if past:
        return max((c for c in candidates if c[0] < today), key=lambda c: c[0])
    first, last = min((c for c in candidates if c[1] >= today), key=lambda c: c[0])
    return max(first, today), last


def _day(
    day: int, month: int, year: str | None, today: date, past: bool
) -> date | None:
    """Return the date of a day written without its year: the next one, or the
    last one for the past; None for an impossible date."""
    try:
        if year:
            return date(int(year), month, day)
        first, _ = _occurrence((month, day), (month, day), today, past)
    except ValueError:  # 31/02, month 13...
        return None
    return first


def _named_day(text: str, today: date, past: bool) -> date | None:
    if match := re.search(rf"\b{_DATE}\b", text):
        return _day(int(match[1]), _MONTHS[match[2]], match[3], today, past)
    if match := re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", text):
        return _day(int(match[1]), int(match[2]), match[3], today, past)
    return None


def _range(text: str, today: date, past: bool) -> Period | None:
    pattern = rf"\b(?:du|entre le) {_DAY}(?: {_MONTH})? (?:au|et le) {_DATE}\b"
    if not (match := re.search(pattern, text)):
        return None
    end = _day(int(match[3]), _MONTHS[match[4]], match[5], today, past)
    if end is None:
        return None
    month = _MONTHS[match[2]] if match[2] else end.month
    start = date(end.year, month, int(match[1]))
    return (start if start <= end else start.replace(year=end.year - 1)), end


def _weekend(today: date, offset: int) -> Period:
    """Return the weekend under way or coming, or ``offset`` weeks after it."""
    # On a Sunday, the Saturday is the day before.
    saturday = today + timedelta(days=5 - today.weekday() + 7 * offset)
    return max(saturday, today), saturday + timedelta(days=1)


def _relative(text: str, today: date) -> Period | None:
    """Return a period counted from today in days, weeks, weekends or months."""
    one_day = timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    if re.search(r"\bhier\b", text):
        return today - one_day, today - one_day
    if "apres-demain" in text:
        return today + 2 * one_day, today + 2 * one_day
    if re.search(r"\bdemain\b", text):
        return today + one_day, today + one_day
    if re.search(
        r"\b(?:aujourd'hui|ce soir|cette nuit|ce matin|cet apres-midi)\b", text
    ):
        return today, today
    if re.search(r"\b(?:ce|le|du) weekend dernier\b", text):
        saturday = monday - timedelta(days=2)
        return saturday, saturday + one_day
    if re.search(r"\b(?:le )?weekend prochain\b", text):
        return _weekend(today, 1 if today.weekday() >= 5 else 0)
    if re.search(r"\b(?:ce|le|du) weekend\b", text):
        return _weekend(today, 0)
    if "semaine derniere" in text:
        return monday - 7 * one_day, monday - one_day
    if "semaine prochaine" in text:
        return monday + 7 * one_day, monday + 13 * one_day
    if "cette semaine" in text:
        return today, monday + 6 * one_day
    if "mois dernier" in text:
        first = (today.replace(day=1) - one_day).replace(day=1)
        return first, _end_of_month(first.year, first.month)
    if "mois prochain" in text:
        first = _end_of_month(today.year, today.month) + one_day
        return first, _end_of_month(first.year, first.month)
    if re.search(r"\bce mois(?:-ci)?\b", text):
        return today, _end_of_month(today.year, today.month)
    return None


def _named(text: str, today: date, past: bool) -> Period | None:
    """Return the next (or last) occurrence of a holiday, season, month or weekday."""
    for name, (start, end) in _HOLIDAYS.items():
        if re.search(rf"\b{name}\b", text):
            return _occurrence(start, end, today, past)
    seasons = rf"\b(?:cet|cette|en|au|l') ?({'|'.join(_SEASONS)})\b"
    if match := re.search(seasons, text):
        return _occurrence(*_SEASONS[match[1]], today, past)
    if match := re.search(rf"\b(?:en|au mois de|mois de) {_MONTH}\b", text):
        month = _MONTHS[match[1]]
        last_day = _end_of_month(2001, month).day  # a common year: February has 28 days
        return _occurrence((month, 1), (month, last_day), today, past)
    weekdays = "|".join(_WEEKDAYS)
    if match := re.search(rf"\b({weekdays})(?: (prochain|dernier))?\b", text):
        ahead = (_WEEKDAYS[match[1]] - today.weekday()) % 7
        if match[2] == "dernier":
            day = today - timedelta(days=(7 - ahead) % 7 or 7)
        else:
            day = today + timedelta(days=ahead or (7 if match[2] == "prochain" else 0))
        return day, day
    return None


def extract_period(question: str, today: date) -> Period | None:
    """Return the period a question asks for, as (first day, last day), either
    end possibly open; None when it gives none."""
    text = _fold(question)
    past = bool(_PAST.search(text))
    if period := _range(text, today, past):
        return period
    if match := re.search(rf"\ba partir du ({_DATE}|{_NUMERIC_DATE})", text):
        start = _named_day(match[1], today, past)
        return (start, None) if start else None
    if match := re.search(rf"\bjusqu'(?:au|a) ({_DATE}|{_NUMERIC_DATE})", text):
        end = _named_day(match[1], today, past)
        return (None, end) if end else None
    if day := _named_day(text, today, past):
        return day, day
    return _relative(text, today) or _named(text, today, past)


# --- Free entry --------------------------------------------------------------

_FREE_REQUEST = re.compile(r"\bgratuit|\b(?:entree|acces) libre\b|\bsans payer\b")


def asks_for_free(question: str) -> bool:
    """Return whether the question asks for free events ("un concert gratuit",
    "en entrée libre")."""
    return bool(_FREE_REQUEST.search(_fold(question)))


# --- Place -------------------------------------------------------------------

# Words that give the type of a venue, not its name ("Couvent des Jacobins").
_VENUE_TYPES = {
    "auditorium",
    "basilique",
    "bibliotheque",
    "cathedrale",
    "chapelle",
    "cinema",
    "cloitre",
    "complexe",
    "couvent",
    "eglise",
    "espace",
    "mediatheque",
    "monument",
    "musee",
    "museum",
    "salle",
    "theatre",
}
_ARTICLES = {"le", "la", "les", "l", "the"}
_PREPOSITIONS = {"de", "des", "du", "d"}


def _words(text: str) -> str:
    """Return ``text`` in lower case, without accents, hyphens and apostrophes
    as spaces, padded with spaces to match whole words."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " " + " ".join(re.sub(r"[-'’]", " ", folded).split()) + " "


# Words that name no place: the city, its département, "lieu" ("Quand a lieu
# ...").
_VAGUE = {_words(CITY).strip(), _words(DEPARTMENT).strip(), "lieu"}


@dataclass(frozen=True)
class Place:
    """A place of the index named by a question."""

    # As written in the index ("Capitole / Arnaud Bernard / Carmes").
    district: str | None = None
    # The distinctive part of the name of a venue ("Jacobins").
    venue: str | None = None


@dataclass(frozen=True)
class _Venue:
    key: str  # distinctive part of the name, as written ("Jacobins")
    full: str  # whole name, folded, for a name a district also uses
    alias: str | None  # compound proper name ending a long name ("Paul-Dupuy")


def _venue(name: str, district_names: set[str]) -> _Venue | None:
    city = re.escape(CITY)
    name = re.sub(
        rf"\s*(?:[-,]|\bde)?\s*{city}$", "", name.strip(), flags=re.IGNORECASE
    )
    words = name.replace("’", "'").split()
    if words and _words(words[0]).strip() in _VENUE_TYPES:
        words = words[1:]
        if words and _words(words[0]).strip() in _PREPOSITIONS:
            words = words[1:]
        elif words and words[0].lower().startswith("d'"):
            words[0] = words[0][2:]
    elif words and _words(words[0]).split()[0] in _ARTICLES:
        # "L'Escale": the name follows the article.
        elided = words[0].lower().startswith("l'")
        words = [words[0][2:], *words[1:]] if elided else words[1:]
    key = " ".join(words)
    if len(key) < 3 or _words(key).strip() in _VAGUE:
        return None
    last = words[-1]
    vague = _words(last).strip() in _VAGUE or _words(last) in district_names
    proper = "-" in last and not vague
    alias = last if len(words) >= 3 and proper else None  # not "Blanche"...
    full = _words(name) if _words(key) in district_names else ""
    return _Venue(key, full, alias)


def _field_values(client: Elasticsearch, index: str, field: str) -> list[str]:
    """Return the values of the keyword ``field`` in ``index``, up to 10,000."""
    aggs = {"values": {"terms": {"field": field, "size": 10_000}}}
    response = client.search(index=index, size=0, aggs=aggs)
    return [bucket["key"] for bucket in response["aggregations"]["values"]["buckets"]]


class PlaceMatcher:
    """Finds the district or the venue a question names, among the known ones."""

    def __init__(self, districts: Sequence[str], venues: Sequence[str]) -> None:
        self.districts = {
            _words(part): district
            for district in districts
            for part in district.split("/")
        }
        self.venues: dict[str, _Venue] = {}
        for name in venues:
            venue = _venue(name, set(self.districts))
            # A capitalized spelling wins.
            if venue and (
                venue.key[:1].isupper() or _words(venue.key) not in self.venues
            ):
                self.venues[_words(venue.key)] = venue

    @classmethod
    def from_index(cls, client: Elasticsearch, index: str) -> "PlaceMatcher":
        """Return a matcher of the districts and venues of the events in ``index``."""
        districts = _field_values(client, index, "district")
        return cls(districts, _field_values(client, index, "venue"))

    def _venue_match(self, question: str, folded: str) -> tuple[str, str] | None:
        """Return the name to filter on and the words matched of the longest
        venue the question names."""
        found = []
        for words, venue in self.venues.items():
            if venue.key.isupper() and len(venue.key) <= 4:  # acronym: capitals only
                if re.search(rf"\b{re.escape(venue.key)}\b", question):
                    found.append((venue.key, words))
                continue
            if venue.full:  # a name a district also uses: only in full
                candidates = [(venue.key, venue.full)]
            else:
                candidates = [(venue.key, words)]
                if venue.alias:
                    candidates.append((venue.alias, _words(venue.alias)))
            found += [(name, text) for name, text in candidates if text in folded]
        return max(found, key=lambda match: len(match[1])) if found else None

    def match(self, question: str) -> Place:
        folded = _words(question)
        venue = self._venue_match(question, folded)
        if venue:
            # its words name no district ("Paul-Dupuy")
            folded = folded.replace(venue[1], " ")
        district = max(
            (
                (words, name)
                for words, name in self.districts.items()
                if words in folded
            ),
            key=lambda match: len(match[0]),
            default=None,
        )
        return Place(
            district=district[1] if district else None,
            venue=venue[0] if venue else None,
        )


def analyze(question: str, today: date, places: PlaceMatcher) -> SearchFilters:
    """Return the constraints of a question asked on ``today``: period, free
    entry, district and venue."""
    start, end = extract_period(question, today) or (None, None)
    place = places.match(question)
    filters = SearchFilters(
        date_from=start,
        date_to=end,
        district=place.district,
        venue=place.venue,
        free=asks_for_free(question) or None,
    )
    return filters.from_today(today)
