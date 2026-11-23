"""The evaluation of the answers: each question of the benchmark searched and
answered by the configuration kept, as of its reference date, and the events
the answer recommends compared with those judged relevant.

The search was measured on its own (``evaluation.retrieval``): this measures
what the LLM does with the events it is given. Exact checks, without a judge:

- recommendation precision: the share of the events recommended that are
  relevant, for a question with at least one recommended;
- recommendation recall: the share of the relevant events given to the LLM
  that it recommends, for a question with at least one given;
- abstention: an out-of-scope question answered without any event.

Then, optionally, the LLM judge of Ragas scores the answers themselves
(``evaluation.judge``).
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from statistics import mean
from typing import TYPE_CHECKING

from cultural_events_rag.assistant import Assistant
from cultural_events_rag.evaluation.dataset import EvalDataset, EvalQuestion
from cultural_events_rag.generation.prompt import event_text

if TYPE_CHECKING:  # Ragas, the eval extra, only to judge
    from cultural_events_rag.evaluation.judge import RagasJudge

logger = logging.getLogger(__name__)

PRECISION, RECALL, ABSTENTION = "precision", "recall", "abstention"
# The metrics of the judge (``evaluation.judge``).
FAITHFULNESS, RELEVANCY, CORRECTNESS = (
    "faithfulness",
    "answer_relevancy",
    "factual_correctness",
)
EXACT, JUDGED = (PRECISION, RECALL, ABSTENTION), (FAITHFULNESS, RELEVANCY, CORRECTNESS)
# The calls to the judge per answer: 2 for faithfulness (the claims, then
# their check), 1 for answer relevancy, 4 for factual correctness (the claims
# of the answer and of the reference, each checked against the other).
JUDGE_CALLS = 7


@dataclass(frozen=True)
class GenerationResult:
    """The answer to a question, the events it recommends and those the LLM
    was given."""

    question: EvalQuestion
    answer: str
    recommended: list[str]  # uids, the most relevant first
    given: list[str]  # uids of the events found, best first
    contexts: list[str] = field(default_factory=list)  # their text, as given
    judged: dict[str, float] = field(default_factory=dict)  # by Ragas

    @property
    def relevant(self) -> set[str]:
        return set(self.question.relevant)

    @property
    def relevant_given(self) -> set[str]:
        return self.relevant.intersection(self.given)

    def metrics(self) -> dict[str, float]:
        """Its metrics, those that apply to it only: precision with an event
        recommended, recall with a relevant event given, abstention out of
        scope."""
        recommended = set(self.recommended)
        if not self.relevant:
            return {ABSTENTION: float(not recommended)}
        scores = {}
        if recommended:
            scores[PRECISION] = len(recommended & self.relevant) / len(recommended)
        if self.relevant_given:
            hits = recommended & self.relevant_given
            scores[RECALL] = len(hits) / len(self.relevant_given)
        return scores


def summary(results: list[GenerationResult]) -> dict[str, tuple[float, int]]:
    """Each metric: its mean over the questions it applies to, and their
    count."""
    scored = [result.metrics() | result.judged for result in results]
    names = (*EXACT, *JUDGED)
    values = {name: [m[name] for m in scored if name in m] for name in names}
    return {name: (mean(v), len(v)) for name, v in values.items() if v}


def evaluate_answers(
    assistant: Assistant, dataset: EvalDataset
) -> list[GenerationResult]:
    """Each question of ``dataset`` asked to ``assistant``, as of its reference
    date."""
    today, results = dataset.reference_date, []
    for number, question in enumerate(dataset.questions, 1):
        retrieval = assistant.search(question.question, today)
        answer = assistant.answer(question.question, today, retrieval)
        results.append(
            GenerationResult(
                question=question,
                answer=answer.text,
                recommended=[event.uid for event in answer.events],
                given=[match.uid for match in retrieval.matches],
                contexts=[event_text(match) for match in retrieval.matches],
            )
        )
        logger.info("Answered %d/%d: %s", number, len(dataset.questions), question.id)
    return results


async def judge_answers(
    results: Sequence[GenerationResult], judge: "RagasJudge"
) -> list[GenerationResult]:
    """The results, those of the questions with relevant events scored by
    ``judge``."""
    judged: list[GenerationResult] = []
    in_scope = len([result for result in results if result.relevant])
    done = 0
    for result in results:
        if result.relevant:
            question = result.question
            scores = await judge.score(
                question.question, result.answer, result.contexts, question.reference
            )
            result = replace(result, judged=scores)
            done += 1
            logger.info("Judged %d/%d: %s", done, in_scope, question.id)
        judged.append(result)
    return judged
