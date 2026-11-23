"""The reranking of the events found: a second, finer sort of the first
candidates of the search, by a cross-encoder model.

The search encodes the question and each chunk apart, so that the vectors of
the chunks are computed once, at indexing. A cross-encoder reads the question
and a chunk together, in one pass of the model, and scores how well the chunk
answers it: far more exact, far too slow for the whole index, hence applied to
the first candidates only.

The model runs on this machine, with sentence-transformers and PyTorch (the
``rerank`` extra): downloaded once from Hugging Face by ``make models``, read
offline then.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from huggingface_hub import snapshot_download

from cultural_events_rag.errors import MissingModelError, RerankerError

if TYPE_CHECKING:  # search calls rerank: the type only, no import cycle
    from cultural_events_rag.retrieval.search import EventMatch

# The cross-encoder of Hugging Face that sorts the first events found again.
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
# The tokens of a pair (question, chunk) the model reads: our chunks, about
# 1000 characters, are 300 to 400 tokens, so none is cut.
MAX_TOKENS = 512
# The files of a cross-encoder it needs: its configuration, its tokenizer, its
# weights in safetensors only (a repository often has them in other formats).
MODEL_FILES = ["*.json", "*.txt", "*.model", "*.safetensors"]


class Reranker(Protocol):
    """Scores how well each text answers a question: the higher, the better."""

    def scores(self, question: str, texts: Sequence[str]) -> list[float]: ...


def _no_loading_bar() -> None:
    """No bar while the weights load, in a few seconds. Display only: skipped
    without transformers."""
    with suppress(ImportError):
        from transformers.utils import logging as transformers_logging

        transformers_logging.disable_progress_bar()  # type: ignore[no-untyped-call]


def download_cross_encoder(model: str) -> str:
    """Download the files ``model`` needs into the cache of Hugging Face: their
    folder."""
    return snapshot_download(model, allow_patterns=MODEL_FILES)


class CrossEncoderReranker:
    """A cross-encoder of Hugging Face, loaded once, at its creation."""

    def __init__(self, model: str) -> None:
        # Imported here: only the rerank extra installs it, and it loads
        # PyTorch, a few seconds.
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
        except OSError as exc:  # not downloaded, and Hugging Face offline
            raise MissingModelError(
                f"no reranker {model} on this machine: run make models"
            ) from exc

    def scores(self, question: str, texts: Sequence[str]) -> list[float]:
        pairs = [(question, text) for text in texts]
        return [float(score) for score in self.encoder.predict(pairs)]


def rerank(
    reranker: Reranker, question: str, matches: Sequence[EventMatch], k: int
) -> list[EventMatch]:
    """The ``k`` best of ``matches`` by the score of ``reranker`` on their best
    chunk, each with that score; their ranks stay those of the search."""
    scores = reranker.scores(question, [match.chunk.page_content for match in matches])
    ranked = sorted(
        zip(matches, scores, strict=True), key=lambda pair: pair[1], reverse=True
    )
    return [replace(match, score=score) for match, score in ranked[:k]]
