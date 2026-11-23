"""The constants tied to the city: its name, département, timezone, cultural
agendas, language and calendar."""

from zoneinfo import ZoneInfo

from cultural_events_rag.models import Agenda

# The city whose events are collected, and its département: neither names a
# place when read in a question.
CITY = "Toulouse"
DEPARTMENT = "Haute-Garonne"
# The timezone the dates of the events are written and read in.
TIMEZONE = ZoneInfo("Europe/Paris")

# The cultural agendas collected, picked by hand. Only their events in CITY are
# kept.
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

# The French names of the days and months, written in the documents and read in
# the questions.
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

# The named periods read in the questions: each name with its first and last
# day, as (month, day). A period whose last day comes before its first spans
# the new year.
DayMonth = tuple[int, int]
# Astronomical seasons of the northern hemisphere, rounded to the day.
SEASONS: dict[str, tuple[DayMonth, DayMonth]] = {
    "printemps": ((3, 20), (6, 20)),
    "été": ((6, 21), (9, 22)),
    "automne": ((9, 23), (12, 20)),
    "hiver": ((12, 21), (3, 19)),
}
# Periods whose dates change every year, at their widest: the Journées du
# patrimoine (third weekend of September); the Toussaint and Noël school
# holidays, from their first Saturday to the Sunday before school; Noël also
# covers the weeks before it.
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
