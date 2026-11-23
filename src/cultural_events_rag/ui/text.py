"""The French texts of the web interface: example questions, errors, badges,
dates, and the filters read in a question."""

from datetime import date, datetime
from typing import Literal

from cultural_events_rag.api.schemas import MAX_QUESTION_LENGTH
from cultural_events_rag.constants import MONTHS, TIMEZONE, WEEKDAYS
from cultural_events_rag.indexing.formatting import format_day, format_time
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.ui.client import ApiError

# From this hour, a slot today is in the evening.
EVENING = 18
SATURDAY = 5  # date.weekday()

# The example questions, each with the icon of its button.
EXAMPLE_QUESTIONS = (
    ("Que faire ce week-end en famille ?", ":material/family_restroom:"),
    ("Un concert gratuit en décembre ?", ":material/music_note:"),
    ("Une expo pendant les vacances de Noël ?", ":material/palette:"),
    ("Un match de rugby du Stade Toulousain ?", ":material/sports_rugby:"),
)

# What the assistant is, shown in the sidebar.
ABOUT = (
    "Projet fictif de démonstration (preuve de concept) d'un assistant RAG, "
    "sans lien avec les organisateurs des événements ni avec Open Agenda. "
    "Les réponses sont rédigées par une IA à partir des agendas publics : "
    "données à titre indicatif, elles peuvent être incomplètes ou inexactes. "
    "Vérifiez la date, le lieu et le tarif sur la page de l'événement avant "
    "de vous déplacer."
)

BadgeColor = Literal["green", "gray"]


def error_message(error: ApiError) -> str:
    if error.timed_out:
        return "L'assistant met trop de temps à répondre. Réessayez dans un instant."
    match error.status_code:
        case None:
            return (
                "L'assistant est injoignable pour le moment. "
                "Réessayez dans quelques instants."
            )
        case 422:
            return (
                "Cette question n'est pas valide : "
                f"de 1 à {MAX_QUESTION_LENGTH} caractères."
            )
        case 502:
            return (
                "Le service de génération ne répond pas. "
                "Réessayez dans quelques instants."
            )
        case 503:
            return (
                "L'assistant n'est pas prêt : l'index des événements est "
                "absent, périmé ou injoignable."
            )
        case status:
            return f"Une erreur inattendue s'est produite (code {status})."


def price_badge(is_free: bool | None) -> tuple[str, BadgeColor]:
    """Return the label of a price and the colour of its badge."""
    match is_free:
        case True:
            return "Gratuit", "green"
        case False:
            return "Payant", "gray"
        case None:
            return "Tarif non précisé", "gray"


def delay(next_slot: datetime, today: date) -> str | None:
    """Return how soon the first slot comes after ``today`` within a week
    (tonight, tomorrow, this weekend, in a few days); None further, or before."""
    moment = next_slot.astimezone(TIMEZONE)
    days = (moment.date() - today).days
    if not 0 <= days < 7:
        return None
    if days == 0:
        return "Ce soir" if moment.hour >= EVENING else "Aujourd'hui"
    if days == 1:
        return "Demain"
    same_week = moment.date().isocalendar()[:2] == today.isocalendar()[:2]
    if same_week and moment.weekday() >= SATURDAY:
        return "Ce week-end"
    return f"Dans {days} jours"


def audience(age_min: int | None, age_max: int | None) -> str | None:
    """Return the ages an event is for, or None when the agenda gives none or 0
    to 99."""
    low = age_min or 0
    high = age_max if age_max is not None and age_max < 99 else None
    if low and high is not None:
        return f"{low}-{high} ans"
    if low:
        return f"Dès {low} ans"
    if high is not None:
        return f"Jusqu'à {high} ans"
    return None


def when(next_slot: datetime, dates: str) -> tuple[bool, str]:
    """Return whether an event is on the day of its tile only, and the text
    beside the tile: its slots then, its dates otherwise."""
    day = format_day(next_slot.astimezone(TIMEZONE).date())
    if dates.startswith(f"{day}, ") and ";" not in dates:
        return True, dates.removeprefix(f"{day}, ")
    return False, dates


def day_tile(next_slot: datetime) -> tuple[str, str, str, str]:
    """Return the tile of the first slot: the weekday shortened, the day of the
    month, the month and the time, in Toulouse."""
    moment = next_slot.astimezone(TIMEZONE)
    day = moment.date()
    weekday = f"{WEEKDAYS[day.weekday()][:3]}."
    return weekday, str(day.day), MONTHS[day.month - 1], format_time(moment)


def waiting_message(requests_per_minute: float | None) -> str:
    """Return the text of the spinner while a question waits for its answer."""
    message = "Recherche des événements et rédaction de la réponse…"
    if requests_per_minute:
        seconds = round(60 / requests_per_minute)
        message += f" Comptez jusqu'à {seconds} s : le quota du modèle de langue."
    return message


def describe_period(filters: SearchFilters, today: date) -> str | None:
    start, end = filters.date_from, filters.date_to
    if start and end:
        if start == end:
            return f"Le {format_day(start)}"
        return f"Du {format_day(start)} au {format_day(end)}"
    if start:
        if start == today:
            return "Événements à venir"
        return f"À partir du {format_day(start)}"
    if end:
        return f"Jusqu'au {format_day(end)}"
    return None


def describe_filters(filters: SearchFilters, today: date) -> list[str]:
    """Return how the question was read, such as ["Du samedi 21 novembre 2026
    au dimanche 22 novembre 2026", "Quartier : Saint-Cyprien"]."""
    parts = [describe_period(filters, today)]
    if filters.district:
        parts.append(f"Quartier : {filters.district}")
    if filters.venue:
        parts.append(f"Lieu : {filters.venue}")
    if filters.free:
        parts.append("Gratuit ou tarif non précisé")
    return [part for part in parts if part]
