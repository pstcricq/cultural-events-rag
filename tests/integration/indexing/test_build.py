"""Tests of the build of the index in a real Elasticsearch, with a fake
embedding model: every document indexed and found, the alias moved, a failed
build leaving the served index unchanged, an old index that cannot be deleted
left aside."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from elasticsearch import ConnectionError as EngineConnectionError
from elasticsearch import Elasticsearch
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from cultural_events_rag.elastic import index_alias
from cultural_events_rag.errors import IncompleteIndexError
from cultural_events_rag.indexing.build import build_index, index_signature
from cultural_events_rag.indexing.documents import events_to_documents
from cultural_events_rag.indexing.store import (
    served_index,
    served_indices,
    signature_differences,
)
from cultural_events_rag.models import Event
from cultural_events_rag.retry import make_retrying
from cultural_events_rag.settings import Settings

FAKE = DeterministicFakeEmbedding(size=16)
FIRST = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
SECOND = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
NO_WAIT = make_retrying("Embedding", retries=1, sleep=lambda _: None)


class RefusingEmbeddings(Embeddings):
    """Refuses every request, as with an invalid key."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        request = httpx.Request("POST", "https://api.mistral.ai/v1/embeddings")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


def _events(event: Event) -> list[Event]:
    jazz = event.model_copy(
        update={
            "uid": "2",
            "title": "Concert de jazz",
            "long_description": "Un trio de jazz joue au conservatoire.",
        }
    )
    return [event, jazz]


def test_the_alias_serves_every_document(
    client: Elasticsearch, settings: Settings, event: Event
) -> None:
    report = build_index(client, _events(event), FAKE, settings, now=FIRST)

    info = served_index(client, index_alias(settings))
    assert info is not None
    assert info.name == report.index
    assert info.count == report.documents == 2
    assert signature_differences(info.meta, index_signature()) == []
    assert info.meta["built_at"] == "2026-11-17T09:00:00+00:00"


def test_a_document_is_found_by_its_words_and_by_its_vector(
    client: Elasticsearch, settings: Settings, event: Event
) -> None:
    build_index(client, _events(event), FAKE, settings, now=FIRST)
    alias = index_alias(settings)

    # "concerts" finds "Concert": the French analyzer stems both.
    lexical = client.search(index=alias, query={"match": {"text": "concerts"}})
    vector = client.search(
        index=alias,
        knn={
            "field": "vector",
            "query_vector": FAKE.embed_query(_events(event)[1].long_description),
            "k": 1,
            "num_candidates": 10,
        },
    )

    assert [hit["_source"]["uid"] for hit in lexical["hits"]["hits"]] == ["2"]
    assert len(vector["hits"]["hits"]) == 1


def test_a_new_build_replaces_the_served_index(
    client: Elasticsearch, settings: Settings, event: Event
) -> None:
    first = build_index(client, _events(event), FAKE, settings, now=FIRST)

    second = build_index(client, [event], FAKE, settings, now=SECOND)

    assert served_indices(client, index_alias(settings)) == [second.index]
    assert second.replaced == [first.index]
    assert second.left == []
    assert not client.indices.exists(index=first.index)


def test_an_old_index_not_deleted_leaves_the_new_one_served(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = build_index(client, _events(event), FAKE, settings, now=FIRST)
    delete = client.indices.delete

    def refuse_first(*, index: str, **kwargs: Any) -> Any:
        if index == first.index:
            raise EngineConnectionError("connection lost")
        return delete(index=index, **kwargs)

    monkeypatch.setattr(client.indices, "delete", refuse_first)

    second = build_index(client, [event], FAKE, settings, now=SECOND)

    assert served_indices(client, index_alias(settings)) == [second.index]
    assert second.left == [first.index]
    assert client.indices.exists(index=first.index)


def test_a_failed_build_leaves_the_served_index(
    client: Elasticsearch, settings: Settings, event: Event
) -> None:
    first = build_index(client, _events(event), FAKE, settings, now=FIRST)

    with pytest.raises(httpx.HTTPStatusError):
        build_index(
            client,
            [event],
            RefusingEmbeddings(),
            settings,
            retrying=NO_WAIT,
            now=SECOND,
        )

    assert served_indices(client, index_alias(settings)) == [first.index]


def test_an_incomplete_build_is_deleted(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = build_index(client, _events(event), FAKE, settings, now=FIRST)
    monkeypatch.setattr(
        "cultural_events_rag.indexing.build.indexed_uids", lambda *_: {"2"}
    )

    with pytest.raises(IncompleteIndexError, match="1 events not indexed: 4154446"):
        build_index(client, _events(event), FAKE, settings, now=SECOND)

    assert served_indices(client, index_alias(settings)) == [first.index]
    assert not client.indices.exists(index=f"{index_alias(settings)}-20261117-100000")


def test_a_document_overwritten_by_another_is_detected(
    client: Elasticsearch,
    settings: Settings,
    event: Event,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def with_a_duplicate(*args: Any) -> list[Document]:
        documents = events_to_documents(*args)
        return [*documents, documents[0]]

    monkeypatch.setattr(
        "cultural_events_rag.indexing.build.events_to_documents", with_a_duplicate
    )

    with pytest.raises(IncompleteIndexError, match="2 entries for 3 documents"):
        build_index(client, _events(event), FAKE, settings, now=FIRST)

    assert served_indices(client, index_alias(settings)) == []
