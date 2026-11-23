"""The ``cultural-events-rag models`` command: the models of Hugging Face the
application runs on this machine, downloaded once into the cache of Hugging
Face: the Mistral tokenizer, that counts the tokens of each embedding request,
and the reranker, unless RERANK_AVAILABLE is false. Every other command runs
Hugging Face offline (make sets HF_HUB_OFFLINE=1): a model missing is
reported, never downloaded on the way."""

import argparse
import sys
from pathlib import Path

from huggingface_hub.errors import HfHubHTTPError

from cultural_events_rag.mistral import TOKENIZER_REPO, download_tokenizer
from cultural_events_rag.retrieval.rerank import RERANK_MODEL, download_cross_encoder
from cultural_events_rag.settings import get_settings


def _size(folder: Path) -> str:
    total = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    return f"{total / 1e9:.1f} GB" if total >= 1e8 else f"{total / 1e6:.0f} MB"


def _models(args: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.rerank_available is None:
        print("FAIL RERANK_AVAILABLE is not set: add it to .env", file=sys.stderr)
        return 1
    try:
        tokenizer = Path(download_tokenizer())
        print(f"Tokenizer: {TOKENIZER_REPO}, {_size(tokenizer.parent)} -> {tokenizer}")
        model = RERANK_MODEL if settings.rerank_available else None
        if model:
            folder = Path(download_cross_encoder(model))
            print(f"Reranker: {model}, {_size(folder)} -> {folder}")
        else:
            print("Reranker: none, RERANK_AVAILABLE is false")
    except (HfHubHTTPError, OSError) as exc:
        print(f"FAIL download from Hugging Face: {exc}", file=sys.stderr)
        return 1
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag models`` to the cultural-events-rag command."""
    models = commands.add_parser(
        "models", help="download the models of Hugging Face run on this machine"
    )
    models.set_defaults(run=_models)
