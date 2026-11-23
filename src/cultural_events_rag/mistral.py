"""The models of the Mistral API the application calls, made from the
settings: the embedding model, that turns the documents into vectors.

The model sits behind its LangChain interface (``Embeddings``), so that
another provider can take its place. ``MistralAIEmbeddings`` batches the
texts, up to 16k tokens per request, counted with the Mistral tokenizer of
Hugging Face: downloaded once by ``make models``, read offline then. Its own
retries, a silent fixed 30 s wait, are turned off: the build retries each
batch itself, visibly, with an exponential backoff.
"""

from huggingface_hub import hf_hub_download
from langchain_core.embeddings import Embeddings
from langchain_mistralai import MistralAIEmbeddings
from tokenizers import Tokenizer

from cultural_events_rag.errors import MissingModelError, MissingSettingError
from cultural_events_rag.settings import Settings

# The model that turns each document into the vector of the index.
EMBEDDING_MODEL = "mistral-embed"

# The tokenizer MistralAIEmbeddings counts the tokens with.
TOKENIZER_REPO = "mistralai/Mixtral-8x7B-v0.1"


def download_tokenizer() -> str:
    """Download the Mistral tokenizer into the cache of Hugging Face: its
    path."""
    return hf_hub_download(TOKENIZER_REPO, "tokenizer.json")


def mistral_tokenizer() -> Tokenizer:
    """The Mistral tokenizer, that MistralAIEmbeddings counts the tokens of
    the texts with, to keep each request under 16k tokens. Loaded here rather
    than by MistralAIEmbeddings, that falls back silently to counting
    characters when it is missing."""
    try:
        return Tokenizer.from_pretrained(TOKENIZER_REPO)
    except OSError as exc:  # not downloaded, and Hugging Face offline
        raise MissingModelError(
            f"no Mistral tokenizer ({TOKENIZER_REPO}) on this machine: run make models"
        ) from exc


def make_embeddings(settings: Settings) -> Embeddings:
    """The Mistral embedding model, EMBEDDING_MODEL."""
    if not settings.mistral_api_key:
        raise MissingSettingError("MISTRAL_API_KEY is not set: add it to .env")
    return MistralAIEmbeddings(
        model=EMBEDDING_MODEL,
        mistral_api_key=settings.mistral_api_key,
        max_retries=None,
        tokenizer=mistral_tokenizer(),
    )
