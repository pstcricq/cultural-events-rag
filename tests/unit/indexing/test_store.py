"""Tests of the index without Elasticsearch: its fields, the name of each
build, a document as an entry, and the signature comparison."""

from datetime import UTC, datetime
from typing import Any

from langchain_core.documents import Document

from cultural_events_rag.indexing.chunking import make_splitter
from cultural_events_rag.indexing.documents import event_to_documents
from cultural_events_rag.indexing.store import (
    bulk_actions,
    index_mappings,
    index_name,
    signature_differences,
    to_source,
)
from cultural_events_rag.models import Event, Location


def test_the_text_is_analyzed_in_french_and_every_vector_compared_by_cosine() -> None:
    mappings = index_mappings(1024, {"embedding_model": "mistral-embed"})
    fields = mappings["properties"]

    assert fields["text"] == {"type": "text", "analyzer": "french"}
    assert fields["vector"]["dims"] == 1024
    assert fields["vector"]["similarity"] == "cosine"
    assert fields["vector"]["index_options"] == {"type": "flat"}  # exact search
    assert fields["timings"] == {"type": "date_range"}
    assert fields["venue"]["fields"]["folded"] == {"type": "text", "analyzer": "folded"}
    assert mappings["dynamic"] == "strict"
    assert mappings["_meta"] == {"embedding_model": "mistral-embed"}


def test_every_metadata_of_a_document_has_a_field(event: Event) -> None:
    [document] = event_to_documents(event, make_splitter(1000, 150))
    fields = index_mappings(4, {})["properties"]

    assert set(to_source(document, [0.0] * 4)) <= set(fields)


def test_each_build_has_its_own_index_behind_the_alias() -> None:
    now = datetime(2026, 11, 17, 9, 5, 3, tzinfo=UTC)

    assert index_name("events", now) == "events-20261117-090503"


def test_a_document_is_stored_with_its_point_and_its_slots(event: Event) -> None:
    [document] = event_to_documents(event, make_splitter(1000, 150))

    source = to_source(document, [0.5, 0.5])

    assert source["text"] == document.page_content
    assert source["vector"] == [0.5, 0.5]
    assert source["location"] == {"lat": 43.600942, "lon": 1.446343}
    assert source["timings"] == [
        {"gte": "2026-06-21T12:30:00+00:00", "lte": "2026-06-21T13:30:00+00:00"}
    ]
    assert "latitude" not in source and "longitude" not in source


def test_a_place_without_coordinates_has_no_point(event: Event) -> None:
    nowhere = event.model_copy(update={"location": Location(city="Toulouse")})
    [document] = event_to_documents(nowhere, make_splitter(1000, 150))

    assert to_source(document, [0.0])["location"] is None


def test_each_entry_keeps_the_id_of_its_document() -> None:
    metadata: dict[str, Any] = {"latitude": None, "longitude": None, "timings": []}
    documents = [
        Document(id=f"1-{i}", page_content="x", metadata=metadata) for i in range(2)
    ]

    actions = list(bulk_actions("events-1", documents, [[0.0], [1.0]]))

    assert [action["_id"] for action in actions] == ["1-0", "1-1"]
    assert {action["_index"] for action in actions} == {"events-1"}


def test_the_signature_differences_are_listed() -> None:
    meta = {"embedding_model": "mistral-embed", "chunk_size": 1000}

    assert signature_differences(meta, meta) == []
    assert signature_differences(meta, meta | {"chunk_size": 500}) == [
        "chunk_size: 1000 instead of 500"
    ]
    assert signature_differences(meta, {"document_format": 1}) == [
        "document_format: None instead of 1"
    ]
