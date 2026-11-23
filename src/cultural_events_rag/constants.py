"""The choices of the project tied to its city, that no setting changes: the
city and its département, its timezone, its cultural agendas, its language
and its calendar. Another city: another version of this file.

The settings (``settings.py``) hold what a user changes, in ``.env``; the
values tied to one piece of code (a batch size, the type of the vector index)
stay next to it.
"""

from zoneinfo import ZoneInfo

from cultural_events_rag.models import Agenda

# The city whose events are collected, and its département: both too vague to
# name a place in a question ("à Toulouse", "en Haute-Garonne").
CITY = "Toulouse"
DEPARTMENT = "Haute-Garonne"
# Its timezone: the dates of its events are written and read in it.
TIMEZONE = ZoneInfo("Europe/Paris")

# Its cultural agendas, picked by hand: agendas outside culture (France
# Travail, local associations) are left out. Some agendas also publish
# elsewhere, hence the filter on the city.
CULTURAL_AGENDAS: tuple[Agenda, ...] = (
    Agenda(36779486, "Bibliothèques de Toulouse"),
    Agenda(20289708, "Musée des Augustins"),
    Agenda(78623851, "Conservatoire à rayonnement régional de Toulouse"),
    Agenda(96583097, "Musée des arts précieux Paul-Dupuy"),
    Agenda(41240026, "SCARE - Syndicat des Cinémas d'Art, de Répertoire et d'Essai"),
    Agenda(9969608, "Shotgun"),
    Agenda(845467, "Le Cratère"),
    Agenda(3513543, "Journées européennes du patrimoine - Occitanie"),
    Agenda(27549140, "Quai des savoirs"),
    Agenda(93202109, "Monuments de Toulouse"),
    Agenda(30183287, "Théâtre Jules-Julien"),
)

# Its language, that of its events and of the questions: the names of the days
# and months, written in the documents and read in the questions, set here
# rather than read from a system locale, often missing in a container.
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

# Its calendar, read in the questions: each name with its first and last day,
# as (month, day). A period whose last day comes before its first runs over
# the new year.
DayMonth = tuple[int, int]
# The astronomical seasons of the northern hemisphere, rounded to the day.
SEASONS: dict[str, tuple[DayMonth, DayMonth]] = {
    "printemps": ((3, 20), (6, 20)),
    "été": ((6, 21), (9, 22)),
    "automne": ((9, 23), (12, 20)),
    "hiver": ((12, 21), (3, 19)),
}
# The days that move from one year to the next are taken at their widest,
# whatever the year: the Journées du patrimoine, the third weekend of
# September; the school holidays of Toussaint and Noël, the same in every
# zone, from the Saturday they start to the Sunday before school. Noël: the
# weeks before it too, those of its markets and concerts.
HOLIDAYS: dict[str, tuple[DayMonth, DayMonth]] = {
    "Halloween": ((10, 31), (10, 31)),
    "Toussaint": ((11, 1), (11, 1)),
    "Noël": ((12, 1), (12, 25)),
    "Nouvel An": ((12, 31), (1, 1)),
    "Fête de la musique": ((6, 21), (6, 21)),
    "Journées du patrimoine": ((9, 15), (9, 22)),
    "Journées européennes du patrimoine": ((9, 15), (9, 22)),
    "vacances de la Toussaint": ((10, 17), (11, 7)),
    "vacances de Toussaint": ((10, 17), (11, 7)),
    "vacances de Noël": ((12, 17), (1, 7)),
}
