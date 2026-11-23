"""The batches of documents sent to the embedding model, the signature of a
build, and a build with no event refused before any request."""

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from cultural_events_rag.errors import IncompleteIndexError
from cultural_events_rag.indexing.build import batches, build_index, index_signature
from cultural_events_rag.indexing.documents import DOCUMENT_FORMAT
from cultural_events_rag.indexing.store import MAPPING_VERSION
from cultural_events_rag.settings import Settings


def doc(length: int) -> Document:
    return Document(page_content="x" * length)


def test_batches_filled_up_to_the_character_budget() -> None:
    documents = [doc(40), doc(40), doc(30), doc(50), doc(10)]

    sizes = [
        [len(d.page_content) for d in b] for b in batches(documents, max_chars=100)
    ]

    assert sizes == [[40, 40], [30, 50, 10]]


def test_oversized_document_goes_alone() -> None:
    sizes = [len(b) for b in batches([doc(10), doc(500), doc(10)], max_chars=100)]

    assert sizes == [1, 1, 1]


def test_the_signature_holds_what_shapes_the_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cultural_events_rag.indexing.build.CHUNK_SIZE", 500)

    assert index_signature() == {
        "embedding_model": "mistral-embed",
        "chunk_size": 500,
        "chunk_overlap": 150,
        "document_format": DOCUMENT_FORMAT,
        "vector_index": "flat",
        "mapping_version": MAPPING_VERSION,
    }


def test_a_build_without_event_is_refused() -> None:
    settings = Settings(_env_file=None, elasticsearch_index="events")

    with pytest.raises(IncompleteIndexError, match="no event to index"):
        build_index(None, [], DeterministicFakeEmbedding(size=4), settings)  # type: ignore[arg-type]
