"""The answer written from the events found, the LLM replaced by a function:
the prompt it reads, the events it recommends kept only when it was given
them, a missing structured output asked again."""

from datetime import date
from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr
from tenacity import Retrying, stop_after_attempt

from cultural_events_rag.errors import GenerationError, MissingSettingError
from cultural_events_rag.generation.answer import (
    STRUCTURED_ATTEMPTS,
    generate,
    looks_cut,
    recommender,
    strip_markdown_emphasis,
)
from cultural_events_rag.generation.prompt import format_context, french_quotes
from cultural_events_rag.mistral import make_chat_model
from cultural_events_rag.retrieval.filters import SearchFilters
from cultural_events_rag.retrieval.search import EventMatch, Retrieval
from cultural_events_rag.settings import Settings

TODAY = date(2026, 10, 19)
ONCE = Retrying(stop=stop_after_attempt(1), reraise=True)


def match(uid: str) -> EventMatch:
    chunk = Document(
        page_content=f"Titre : {uid}\n\nUn morceau.",
        metadata={"event_text": f"Titre : {uid}\n\nToute la description."},
    )
    return EventMatch(uid=uid, score=1.0, chunk=chunk, ranks={})


RETRIEVAL = Retrieval(filters=SearchFilters(), matches=[match("a"), match("b")])


def model(*outputs: Any) -> tuple[RunnableLambda[Any, Any], list[PromptValue]]:
    """A model returning ``outputs`` in turn, and the prompts it read."""
    prompts: list[PromptValue] = []
    answers = iter(outputs)

    def answer(prompt: PromptValue) -> Any:
        prompts.append(prompt)
        return next(answers)

    return RunnableLambda(answer), prompts


def test_the_llm_reads_each_event_whole_with_its_uid() -> None:
    assert format_context([match("a")]) == (
        '<event uid="a">\nTitre : a\n\nToute la description.\n</event>'
    )
    assert format_context([]) == "(aucun événement)"


def test_the_llm_reads_french_quotes_only() -> None:
    quoted = match("a")
    quoted.chunk.metadata["event_text"] = 'Surnommé "Chapelle Sixtine", un 12" vinyle.'

    assert format_context([quoted]) == (
        '<event uid="a">\nSurnommé « Chapelle Sixtine », un 12” vinyle.\n</event>'
    )
    assert french_quotes('" Le Cid "') == "« Le Cid »"


def test_the_prompt_holds_the_day_the_events_and_the_question() -> None:
    llm, prompts = model({"answer": "Voici.", "event_uids": []})

    generate(llm, "Un concert ?", TODAY, RETRIEVAL, ONCE)

    [system, human] = prompts[0].to_messages()
    assert "Nous sommes le lundi 19 octobre 2026." in str(system.content)
    assert "à Toulouse" in str(system.content)
    assert '<event uid="b">\nTitre : b\n\nToute la description.' in str(system.content)
    assert human.content == "Un concert ?"


def test_the_question_reaches_the_llm_with_french_quotes() -> None:
    llm, prompts = model({"answer": "Voici.", "event_uids": []})

    generate(llm, 'Un spectacle "Le Cid" ?', TODAY, RETRIEVAL, ONCE)

    assert prompts[0].to_messages()[1].content == "Un spectacle « Le Cid » ?"


def test_only_the_events_given_are_recommended_once_each_in_order() -> None:
    llm, _ = model({"answer": "B puis A.", "event_uids": ["b", "x", "a", "b"]})

    answer = generate(llm, "Un concert ?", TODAY, RETRIEVAL, ONCE)

    assert answer.text == "B puis A."
    assert [event.uid for event in answer.events] == ["b", "a"]
    assert answer.retrieval is RETRIEVAL


def test_a_missing_structured_output_is_asked_again() -> None:
    llm, prompts = model(None, {"answer": "Rien ne convient.", "event_uids": []})

    answer = generate(llm, "Un restaurant ?", TODAY, RETRIEVAL, ONCE)

    assert len(prompts) == 2
    assert answer.events == []


def test_no_structured_output_at_all_fails() -> None:
    llm, _ = model(*[None] * STRUCTURED_ATTEMPTS)

    with pytest.raises(GenerationError, match="no structured answer"):
        generate(llm, "Un concert ?", TODAY, RETRIEVAL, ONCE)


def test_an_answer_cut_in_the_middle_of_a_sentence_is_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm, _ = model({"answer": "Une visite de ce lieu surnommé la ", "event_uids": []})

    answer = generate(llm, "Aux Carmélites ?", TODAY, RETRIEVAL, ONCE)

    assert answer.events == []
    assert "looks cut off" in caplog.text


@pytest.mark.parametrize(
    "text",
    ["Voici.", "Lequel ?", "Au « Cratère »", "(gratuit) ", "Annulé.*", "Fin. __"],
)
def test_a_whole_answer_does_not_look_cut(text: str) -> None:
    assert not looks_cut(text)


@pytest.mark.parametrize("text", ["Surnommé la ", "Voici les événements :", ""])
def test_an_unfinished_answer_looks_cut(text: str) -> None:
    assert looks_cut(text)


def test_the_markdown_emphasis_is_removed() -> None:
    text = "Un **concert** de __jazz__, *gratuit*, 2 * 3 places."

    assert strip_markdown_emphasis(text) == "Un concert de jazz, gratuit, 2 * 3 places."


def test_the_chat_model_from_the_settings() -> None:
    settings = Settings(
        _env_file=None, mistral_api_key=SecretStr("secret"), llm_requests_per_minute=2
    )

    llm = make_chat_model(settings)

    assert llm.model_dump()["model"] == "ministral-14b-latest"
    assert llm.model_dump()["temperature"] == 0
    assert llm.model_dump()["max_retries"] == 1  # retried by the caller
    recommender(llm)  # its structured output, built without a call


def test_the_chat_model_needs_the_key() -> None:
    with pytest.raises(MissingSettingError, match="MISTRAL_API_KEY"):
        make_chat_model(Settings(_env_file=None))
