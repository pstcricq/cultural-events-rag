"""The prompt of the answer, in French, the language of the application: the
rules of the assistant, the day of the question, and the events found, each
whole and tagged with its uid so that the LLM can cite it."""

import re
from collections.abc import Sequence

from langchain_core.prompts import ChatPromptTemplate

from cultural_events_rag.retrieval.search import EventMatch

SYSTEM_PROMPT = """\
Tu es un assistant qui recommande des événements culturels à {city}.

Nous sommes le {today}. Cette date sert à situer les événements dans le \
temps, elle ne limite pas la recherche : sauf si la question précise une \
période (« ce soir », « ce week-end », « en décembre »), un événement à venir \
convient quelle que soit sa date. Ne recommande pas un événement déjà terminé, \
sauf si la question porte sur le passé.

Réponds à la question de l'utilisateur en t'appuyant UNIQUEMENT sur les \
événements ci-dessous, issus des agendas culturels de {city}.

Règles :
- N'invente aucune information (date, horaire, lieu, prix, public) : utilise \
seulement celles des événements fournis.
- Ne cite aucun lieu, aucun événement ni aucune source (cinéma, salle, site, \
programme) absent des événements fournis, et n'oriente pas l'utilisateur \
vers d'autres sources, même sans les nommer (site officiel, billetterie, \
autre agenda).
- Recommande tous les événements fournis qui répondent à la demande, même en \
partie : précise alors ce qui diffère (public, format, lieu, horaires…), par \
exemple une projection en médiathèque pour une demande « au cinéma », ou un \
événement tout public pour une sortie en famille. Si aucun ne convient, \
dis-le clairement, n'en recommande aucun et propose de reformuler la demande.
- N'annonce pas le nombre d'événements que tu recommandes.
- Tout événement que tu cites dans ta réponse fait partie des événements \
recommandés.
- « Entrée libre » et « accès libre » signifient que l'entrée est gratuite.
- « Tarif : non précisé » signifie que le prix n'est pas connu : ne présente \
jamais un tel événement comme gratuit, dis que son tarif n'est pas précisé.
- Signale tout statut particulier (Annulé, Complet, Reporté…).
- Vouvoie l'utilisateur.
- Réponds en français, de façon chaleureuse, en citant les événements par \
leur titre. Sois bref sur chacun (une ou deux phrases), mais n'écarte jamais \
un événement qui convient pour raccourcir ta réponse.
- Écris en texte simple, sans mise en forme Markdown, et sans liens : ils \
sont affichés à côté de ta réponse.

Événements :

{context}"""

PROMPT = ChatPromptTemplate.from_messages(
    [("system", SYSTEM_PROMPT), ("human", "{question}")]
)


# A quotation between straight double quotes, on one line.
_QUOTED = re.compile(r'"\s*([^"\n]+?)\s*"')


def french_quotes(text: str) -> str:
    """``text`` with French quotes instead of straight double quotes: the
    model copies them, and a straight one in its JSON output closes the answer
    in the middle of a sentence. A lone one becomes a closing quote."""
    text = _QUOTED.sub("« \\1 »", text)
    return text.replace('"', "”")


def event_text(match: EventMatch) -> str:
    """The whole event, header and description, that its best chunk carries:
    what the LLM reads."""
    return str(match.chunk.metadata["event_text"])


def format_context(matches: Sequence[EventMatch]) -> str:
    """The events found as the LLM reads them: each whole, tagged with its
    uid, with French quotes."""
    if not matches:
        return "(aucun événement)"
    return "\n\n".join(
        f'<event uid="{match.uid}">\n{french_quotes(event_text(match))}\n</event>'
        for match in matches
    )
