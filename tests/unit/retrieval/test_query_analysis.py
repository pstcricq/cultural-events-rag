"""The analysis of a question: its period, computed from the day it is asked,
whether it asks for free events, the district or the venue it names, and the
filters they all make."""

from datetime import date

import pytest

from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.query_analysis import (
    Place,
    PlaceMatcher,
    analyze,
    asks_for_free,
    extract_period,
)

TODAY = date(2026, 10, 15)  # a Thursday, the day of the benchmark questions


# --- Free entry --------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Un concert gratuit ?", True),
        ("Des sorties GRATUITES en décembre", True),
        ("Une expo en entrée libre", True),
        ("Que faire sans payer ?", True),
        ("Que faire ce week-end ?", False),
    ],
)
def test_asks_for_free(question: str, expected: bool) -> None:
    assert asks_for_free(question) is expected


# --- Filters -----------------------------------------------------------------


def test_the_analysis_gives_every_constraint() -> None:
    places = PlaceMatcher(["Saint-Cyprien"], ["Médiathèque José Cabanis"])

    filters = analyze("Un concert gratuit ce week-end à Saint-Cyprien ?", TODAY, places)

    assert filters == SearchFilters(
        date_from=date(2026, 10, 17),
        date_to=date(2026, 10, 18),
        district="Saint-Cyprien",
        free=True,
    )


def test_a_question_without_constraint_looks_from_today() -> None:
    places = PlaceMatcher([], [])

    assert analyze("Un concert de harpe", TODAY, places) == SearchFilters(
        date_from=TODAY
    )


def test_a_question_about_the_past_keeps_its_period() -> None:
    places = PlaceMatcher([], [])

    filters = analyze("Les concerts du mois dernier ?", TODAY, places)

    assert (filters.date_from, filters.date_to) == (date(2026, 9, 1), date(2026, 9, 30))


# --- Periods -----------------------------------------------------------------
# A period under way starts at today, unless the question is about the past.

Period = tuple[date | None, date | None] | None


def d(month: int, day: int, year: int = 2026) -> date:
    return date(year, month, day)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # Days
        ("Que faire aujourd'hui ?", (d(10, 15), d(10, 15))),
        ("Un concert ce soir ?", (d(10, 15), d(10, 15))),
        ("Que faire cette nuit ?", (d(10, 15), d(10, 15))),
        ("Une expo demain ?", (d(10, 16), d(10, 16))),
        ("Que faire après-demain ?", (d(10, 17), d(10, 17))),
        # Weekdays: next occurrence, today included ("prochain": strictly after today)
        ("Un concert samedi ?", (d(10, 17), d(10, 17))),
        ("Que faire dimanche ?", (d(10, 18), d(10, 18))),
        ("Un spectacle mardi ?", (d(10, 20), d(10, 20))),
        ("Un atelier jeudi ?", (d(10, 15), d(10, 15))),
        ("Que faire samedi prochain ?", (d(10, 17), d(10, 17))),
        ("Un atelier jeudi prochain ?", (d(10, 22), d(10, 22))),
        # Weekends and weeks
        ("Que faire ce week-end ?", (d(10, 17), d(10, 18))),
        ("Que faire ce weekend en famille ?", (d(10, 17), d(10, 18))),
        ("Une sortie le week-end ?", (d(10, 17), d(10, 18))),
        ("Que faire le week-end prochain ?", (d(10, 17), d(10, 18))),
        ("Que faire cette semaine ?", (d(10, 15), d(10, 18))),
        ("Que faire la semaine prochaine ?", (d(10, 19), d(10, 25))),
        # Months: next occurrence, the current one from today
        ("Que faire ce mois-ci ?", (d(10, 15), d(10, 31))),
        ("Des sorties le mois prochain ?", (d(11, 1), d(11, 30))),
        ("Quelles sorties en décembre ?", (d(12, 1), d(12, 31))),
        ("Que faire en octobre ?", (d(10, 15), d(10, 31))),
        ("Des concerts en mars ?", (d(3, 1, 2027), d(3, 31, 2027))),
        # Seasons: next occurrence, the current one from today
        ("Que faire cet automne ?", (d(10, 15), d(12, 20))),
        ("Une expo cet hiver ?", (d(12, 21), d(3, 19, 2027))),
        ("Des festivals au printemps ?", (d(3, 20, 2027), d(6, 20, 2027))),
        # Explicit dates: next occurrence when the year is not given
        ("Que faire le 24 octobre ?", (d(10, 24), d(10, 24))),
        ("Un concert samedi 24 octobre ?", (d(10, 24), d(10, 24))),
        ("Un concert le 3 décembre ?", (d(12, 3), d(12, 3))),
        ("Qu'y a-t-il le 1er novembre ?", (d(11, 1), d(11, 1))),
        ("Une sortie le 24/10 ?", (d(10, 24), d(10, 24))),
        ("Une expo le 12/03/2027 ?", (d(3, 12, 2027), d(3, 12, 2027))),
        ("Un spectacle le 10 octobre ?", (d(10, 10, 2027), d(10, 10, 2027))),
        # Ranges and open periods
        ("Que faire du 20 au 25 octobre ?", (d(10, 20), d(10, 25))),
        ("Des sorties entre le 1er et le 15 novembre ?", (d(11, 1), d(11, 15))),
        ("Que faire à partir du 1er novembre ?", (d(11, 1), None)),
        ("Des expos jusqu'au 31 octobre ?", (None, d(10, 31))),
        # Holidays: next occurrence
        ("Des événements pour Halloween ?", (d(10, 31), d(10, 31))),
        ("Que faire à la Toussaint ?", (d(11, 1), d(11, 1))),
        ("Que faire à Noël ?", (d(12, 1), d(12, 25))),  # its markets too
        ("Une soirée pour le Nouvel An ?", (d(12, 31), d(1, 1, 2027))),
        ("Des concerts pour la Fête de la musique ?", (d(6, 21, 2027), d(6, 21, 2027))),
        # Questions about the past: the most recent occurrence, whole
        ("Qu'y avait-il hier ?", (d(10, 14), d(10, 14))),
        ("Qu'y avait-il en juin ?", (d(6, 1), d(6, 30))),
        ("Les concerts du mois dernier ?", (d(9, 1), d(9, 30))),
        ("Qu'y avait-il la semaine dernière ?", (d(10, 5), d(10, 11))),
        ("Que s'est-il passé le week-end dernier ?", (d(10, 10), d(10, 11))),
        ("Qu'y avait-il samedi dernier ?", (d(10, 10), d(10, 10))),
        (
            "Qu'est-ce qu'il y avait aux Journées du patrimoine ?",
            (d(9, 15), d(9, 22)),  # the third weekend of September, at the widest
        ),
        # School holidays, at their widest whatever the year
        ("Que faire pendant les vacances de la Toussaint ?", (d(10, 17), d(11, 7))),
        ("Pendant les vacances de Noël ?", (d(12, 17), d(1, 7, 2027))),
        ("Qu'y avait-il aux vacances de Noël ?", (d(12, 17, 2025), d(1, 7))),
        # No period: a kind of event, a number or a name is not a date
        ("Je cherche une soirée techno à Toulouse", None),
        ("Un atelier du soir", None),
        ("Une visite le matin", None),
        ("Une activité pour un enfant de 6 ans", None),
        ("Les 24h de l'accordéon", None),
        ("La Nuit des Diaboliques", None),
        ("Que faire au Weekend Famille ?", None),
        ("Un concert à venir", None),
        ("Que faire prochainement ?", None),
        ("Un film des années 2000", None),
        ("Un concert de harpe", None),
    ],
)
def test_period(question: str, expected: Period) -> None:
    assert extract_period(question, TODAY) == expected


SATURDAY = date(2026, 10, 17)
SUNDAY = date(2026, 10, 18)
NEW_YEAR_EVE = date(2026, 12, 30)  # a Wednesday


@pytest.mark.parametrize(
    ("question", "today", "expected"),
    [
        ("Que faire ce week-end ?", SATURDAY, (d(10, 17), d(10, 18))),
        ("Que faire ce week-end ?", SUNDAY, (d(10, 18), d(10, 18))),
        ("Que faire le week-end prochain ?", SATURDAY, (d(10, 24), d(10, 25))),
        ("Que faire le week-end prochain ?", SUNDAY, (d(10, 24), d(10, 25))),
        ("Un concert samedi ?", SATURDAY, (d(10, 17), d(10, 17))),
        ("Que faire demain ?", SATURDAY, (d(10, 18), d(10, 18))),
        ("Que faire cette semaine ?", SUNDAY, (d(10, 18), d(10, 18))),
        ("Des sorties en janvier ?", NEW_YEAR_EVE, (d(1, 1, 2027), d(1, 31, 2027))),
        (
            "Des sorties le mois prochain ?",
            NEW_YEAR_EVE,
            (d(1, 1, 2027), d(1, 31, 2027)),
        ),
        (
            "Que faire la semaine prochaine ?",
            NEW_YEAR_EVE,
            (d(1, 4, 2027), d(1, 10, 2027)),
        ),
        ("Une soirée pour le Nouvel An ?", NEW_YEAR_EVE, (d(12, 31), d(1, 1, 2027))),
        ("Une expo cet hiver ?", NEW_YEAR_EVE, (d(12, 30), d(3, 19, 2027))),
    ],
    ids=lambda value: value.isoformat() if isinstance(value, date) else None,
)
def test_period_depends_on_today(question: str, today: date, expected: Period) -> None:
    assert extract_period(question, today) == expected


# --- Place -------------------------------------------------------------------
# The question compared with the districts and venues of the index, ignoring
# case, accents and hyphens. A venue is named by the distinctive part of its
# name ("Jacobins" for "Couvent des Jacobins"), which then filters every
# spelling of it.

REAL_DISTRICTS = [
    "Capitole / Arnaud Bernard / Carmes",
    "Saint-Cyprien",
    "Lardenne / Pradettes / Basso-Cambo",
    "Les Chalets / Bayard / Belfort / Saint-Aubin / Dupuy",
    "Saint-Michel / Le Busca / Empalot / Saint-Agne / Ile du Ramier",
    "Toulouse Centre",
]
REAL_VENUES = [
    "Couvent des Jacobins",
    "Chapelle des Carmélites",
    "chapelle des carmélites",
    "Musée des Augustins",
    "Musée des Arts Précieux Paul-Dupuy",
    "Médiathèque Saint-Cyprien",
    "Médiathèque Pradettes",
    "Médiathèque José Cabanis",
    "Le Cratère",
    "Le Cratère - Toulouse",
    "Quai des Savoirs - Toulouse",
    "Théâtre Jules Julien",
    "Chapelle de La Grave",
    "ABC",
    "CRR",
    "Toulouse",
    "Lieu",
    "Complexe La Voile Blanche",
    "Archives départementales de la Haute-Garonne",
]


@pytest.fixture
def places() -> PlaceMatcher:
    return PlaceMatcher(REAL_DISTRICTS, REAL_VENUES)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # Venues, by the distinctive part of their name
        ("Que faire au couvent des Jacobins ?", Place(venue="Jacobins")),
        ("Un concert aux Jacobins ?", Place(venue="Jacobins")),
        ("Quels événements à la chapelle des Carmélites ?", Place(venue="Carmélites")),
        ("Que voir au musée des Augustins ?", Place(venue="Augustins")),
        ("Une projection au Cratère ?", Place(venue="Cratère")),
        ("Que faire au Quai des Savoirs ?", Place(venue="Quai des Savoirs")),
        ("Que faire à la médiathèque José Cabanis ?", Place(venue="José Cabanis")),
        ("Un spectacle au théâtre Jules-Julien ?", Place(venue="Jules Julien")),
        ("Une visite à la chapelle de La Grave ?", Place(venue="La Grave")),
        # A long name: its last word is enough ("Paul-Dupuy", not the district "Dupuy")
        ("Un atelier au musée Paul-Dupuy ?", Place(venue="Paul-Dupuy")),
        # Acronyms: in capitals only
        ("Un film à l'ABC ?", Place(venue="ABC")),
        ("Un concert au CRR ?", Place(venue="CRR")),
        ("Apprendre l'abc du dessin", Place()),
        # Districts, by one of the neighbourhoods they group
        ("Que faire dans le quartier Saint-Cyprien ?", Place(district="Saint-Cyprien")),
        (
            "Que faire aux Carmes ?",
            Place(district="Capitole / Arnaud Bernard / Carmes"),
        ),
        (
            "Une sortie près du Capitole ?",
            Place(district="Capitole / Arnaud Bernard / Carmes"),
        ),
        (
            "Que faire à Pradettes ?",
            Place(district="Lardenne / Pradettes / Basso-Cambo"),
        ),
        (
            "Que faire à Saint-Agne ?",
            Place(
                district="Saint-Michel / Le Busca / Empalot / Saint-Agne / Ile du Ramier"
            ),
        ),
        # A district name used by a venue: the venue only when the question names it fully
        ("Que faire à la médiathèque Saint-Cyprien ?", Place(venue="Saint-Cyprien")),
        ("Que faire à la médiathèque Pradettes ?", Place(venue="Pradettes")),
        # No place: the city, generic venue names, words that are not places
        ("Que faire à Toulouse ce soir ?", Place()),
        ("Quand a lieu Harpissima ?", Place()),
        ("Un concert de jazz", Place()),
        ("Une nuit blanche ?", Place()),  # only a compound name ends a long name
        ("Une conférence en Haute-Garonne ?", Place()),
        ("Une activité pour un enfant de 6 ans", Place()),
    ],
)
def test_place(places: PlaceMatcher, question: str, expected: Place) -> None:
    assert places.match(question) == expected
