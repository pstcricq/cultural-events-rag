"""The choices of the project tied to its city, that no setting changes: the
city and its cultural agendas. Another city: another version of this file.

The settings (``settings.py``) hold what a user changes, in ``.env``; the
values tied to one piece of code (a batch size, the type of the vector index)
stay next to it.
"""

from cultural_events_rag.models import Agenda

# The city whose events are collected.
CITY = "Toulouse"

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
