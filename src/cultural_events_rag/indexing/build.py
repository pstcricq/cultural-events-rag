"""The build of the index: the events turned into documents, embedded batch by
batch and written into a new index, then the alias moved onto it once every
event is in it. Each batch is one embedding request, retried on a transient
error."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from elasticsearch import Elasticsearch, helpers
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from tenacity import Retrying

from cultural_events_rag.elastic import index_alias
from cultural_events_rag.errors import IncompleteIndexError
from cultural_events_rag.indexing.chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    make_splitter,
)
from cultural_events_rag.indexing.documents import (
    DOCUMENT_FORMAT,
    events_to_documents,
)
from cultural_events_rag.indexing.store import (
    INDEX_SETTINGS,
    MAPPING_VERSION,
    VECTOR_INDEX,
    bulk_actions,
    delete_indices,
    index_mappings,
    index_name,
    indexed_uids,
    move_alias,
)
from cultural_events_rag.mistral import EMBEDDING_MODEL
from cultural_events_rag.models import Event
from cultural_events_rag.retry import make_retrying
from cultural_events_rag.settings import Settings

# Batches of about 15k tokens, about 2.7 characters per token on French text:
# one request each, under the 16k tokens of the Mistral client.
MAX_BATCH_CHARS = 40_000

Progress = Callable[[int, int], None]  # (documents done, documents in all)


def index_signature() -> dict[str, Any]:
    """Return the signature of the index: what it depends on besides the events."""
    return {
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "document_format": DOCUMENT_FORMAT,
        "vector_index": VECTOR_INDEX,
        "mapping_version": MAPPING_VERSION,
    }


def batches(
    documents: Sequence[Document], max_chars: int = MAX_BATCH_CHARS
) -> Iterator[list[Document]]:
    """Split the documents into consecutive batches of up to ``max_chars``
    characters; a longer document makes a batch of its own."""
    batch: list[Document] = []
    size = 0
    for document in documents:
        length = len(document.page_content)
        if batch and size + length > max_chars:
            yield batch
            batch, size = [], 0
        batch.append(document)
        size += length
    if batch:
        yield batch


@dataclass(frozen=True)
class BuildReport:
    """The index a build wrote, its document count, the indices it replaced and
    those that could not be deleted."""

    index: str
    documents: int
    replaced: list[str]
    left: list[str]


def build_index(
    client: Elasticsearch,
    events: Sequence[Event],
    embeddings: Embeddings,
    settings: Settings,
    on_progress: Progress | None = None,
    retrying: Retrying | None = None,
    max_batch_chars: int = MAX_BATCH_CHARS,
    now: datetime | None = None,
) -> BuildReport:
    """Write the documents of ``events`` and their vectors into a new index,
    then move the alias of the settings onto it once every document is in it.

    On a failure before the move, the new index is deleted and the alias is
    unchanged. The indices the alias served are deleted afterwards; a failure
    there leaves them in place."""
    alias = index_alias(settings)
    split = make_splitter(CHUNK_SIZE, CHUNK_OVERLAP)
    documents = events_to_documents(events, split)
    if not documents:
        raise IncompleteIndexError("no event to index")
    retrying = retrying or make_retrying("Embedding")
    signature = index_signature()
    built_at = (now or datetime.now(UTC)).replace(microsecond=0)
    index = index_name(alias, built_at)
    created = False
    try:
        done = 0
        for batch in batches(documents, max_batch_chars):
            texts = [document.page_content for document in batch]
            vectors = retrying(embeddings.embed_documents, texts)
            if not created:
                meta = signature | {"built_at": built_at.isoformat()}
                client.indices.create(
                    index=index,
                    settings=INDEX_SETTINGS,
                    mappings=index_mappings(len(vectors[0]), meta),
                )
                created = True
            helpers.bulk(client, bulk_actions(index, batch, vectors))
            done += len(batch)
            if on_progress:
                on_progress(done, len(documents))
        client.indices.refresh(index=index)
        missing = sorted(
            {event.uid for event in events} - indexed_uids(client, index, len(events))
        )
        if missing:
            listed = ", ".join(missing[:10])
            raise IncompleteIndexError(f"{len(missing)} events not indexed: {listed}")
        # Two documents with the same id: the second overwrote the first.
        count = client.count(index=index)["count"]
        if count != len(documents):
            raise IncompleteIndexError(
                f"{count} entries for {len(documents)} documents"
            )
        replaced = move_alias(client, alias, index)
    except BaseException:
        if created:
            client.indices.delete(index=index, ignore_unavailable=True)
        raise
    left = delete_indices(client, replaced)
    return BuildReport(
        index=index, documents=len(documents), replaced=replaced, left=left
    )
