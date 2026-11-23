"""The reranking of the events found: the first candidates of the search sorted
again by a cross-encoder, which reads the question and a chunk together.

The model runs locally with sentence-transformers and PyTorch (the ``rerank``
extra), from the Hugging Face cache."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from huggingface_hub import snapshot_download

from cultural_events_rag.errors import MissingModelError, RerankerError

if TYPE_CHECKING:  # type only: search imports this module
    from cultural_events_rag.retrieval.search import EventMatch

# The cross-encoder of Hugging Face.
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
# The maximum tokens of a (question, chunk) pair; a chunk is 300 to 400 tokens.
MAX_TOKENS = 512
# The files of the model: its configuration, its tokenizer, and its weights in
# safetensors.
MODEL_FILES = ["*.json", "*.txt", "*.model", "*.safetensors"]


class Reranker(Protocol):
    """Scores how well each text answers a question: the higher, the better."""

    def scores(self, question: str, texts: Sequence[str]) -> list[float]: ...


def _no_loading_bar() -> None:
    """Hide the progress bar of transformers while the weights load; does
    nothing without transformers."""
    with suppress(ImportError):
        from transformers.utils import logging as transformers_logging

        transformers_logging.disable_progress_bar()  # type: ignore[no-untyped-call]


def download_cross_encoder(model: str) -> str:
    """Download the files of ``model`` into the Hugging Face cache and return
    their folder."""
    return snapshot_download(model, allow_patterns=MODEL_FILES)


class CrossEncoderReranker:
    """A cross-encoder of Hugging Face, loaded once, at its creation."""

    def __init__(self, model: str) -> None:
        # Imported here: only the rerank extra installs it.
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerError(
                "the reranking needs the rerank extra: run make install"
            ) from exc

        _no_loading_bar()
        self.model = model
        try:
            self.encoder = CrossEncoder(model, max_length=MAX_TOKENS)
        except OSError as exc:  # not downloaded, Hugging Face offline
            raise MissingModelError(
                f"no reranker {model} on this machine: run make models"
            ) from exc

    def scores(self, question: str, texts: Sequence[str]) -> list[float]:
        pairs = [(question, text) for text in texts]
        return [float(score) for score in self.encoder.predict(pairs)]


def rerank(
    reranker: Reranker, question: str, matches: Sequence[EventMatch], k: int
) -> list[EventMatch]:
    """Return the ``k`` best of ``matches`` by the score of ``reranker`` on
    their best chunk, each with that score; their ranks are those of the
    search."""
    scores = reranker.scores(question, [match.chunk.page_content for match in matches])
    ranked = sorted(
        zip(matches, scores, strict=True), key=lambda pair: pair[1], reverse=True
    )
    return [replace(match, score=score) for match, score in ranked[:k]]
