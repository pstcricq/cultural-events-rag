"""The Elasticsearch index of the events: one entry per document, with its
French text for the lexical search (BM25), its vector for the vector search
(kNN) and the metadata filtered on.

Each build writes a new index named after the alias and the build time, then
moves the alias onto it. The signature of a build is stored in the ``_meta`` of
its index."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from elasticsearch import ApiError, Elasticsearch, NotFoundError, TransportError
from langchain_core.documents import Document

# One shard, no replica. The folded analyzer splits a name into lowercase words
# without accents nor elisions: "Chapelle des Carmélites" matches "carmelites".
INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "analyzer": {
            "folded": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "elision", "asciifolding"],
            }
        }
    },
}

# The version of the fields below, in the signature of each index; raised at
# each change.
MAPPING_VERSION = 1

# Exact vector search: the question compared with every vector, by cosine.
VECTOR_INDEX = "flat"


def index_mappings(dims: int, signature: dict[str, Any]) -> dict[str, Any]:
    """Return the mappings of an index whose vectors have ``dims`` dimensions;
    any other field is refused."""
    keyword = {"type": "keyword"}
    stored = {"type": "keyword", "index": False}  # returned, not searched
    folded = {"type": "text", "analyzer": "folded"}
    return {
        "_meta": signature,
        "dynamic": "strict",
        "properties": {
            # French analyzer: elisions, stop words, light stemming.
            "text": {"type": "text", "analyzer": "french"},
            # The whole text of the event, the same in each of its chunks; not
            # searched.
            "event_text": {"type": "text", "index": False},
            "vector": {
                "type": "dense_vector",
                "dims": dims,
                "index": True,
                "similarity": "cosine",
                "index_options": {"type": VECTOR_INDEX},
            },
            "uid": keyword,
            "title": {"type": "text", "analyzer": "french"},
            "url": stored,
            "agenda": keyword,
            # The exact name, and its words for a filter on part of it.
            "venue": {"type": "keyword", "fields": {"folded": folded}},
            "address": stored,
            "district": keyword,
            "city": keyword,
            "location": {"type": "geo_point"},
            "first_begin": {"type": "date"},
            "last_end": {"type": "date"},
            # Each slot as a date range.
            "timings": {"type": "date_range"},
            "status": keyword,
            "age_min": {"type": "integer"},
            "age_max": {"type": "integer"},
            "keywords": keyword,
            "is_free": {"type": "boolean"},
            "chunk_index": {"type": "integer"},
            "chunk_count": {"type": "integer"},
        },
    }


def index_name(alias: str, now: datetime) -> str:
    """Return the name of the index a build at ``now`` writes behind ``alias``."""
    return f"{alias}-{now:%Y%m%d-%H%M%S}"


def to_source(document: Document, vector: list[float]) -> dict[str, Any]:
    """Return the entry of a document: its text, its vector and its metadata,
    the coordinates as a point and each slot as a date range."""
    metadata = dict(document.metadata)
    latitude, longitude = metadata.pop("latitude"), metadata.pop("longitude")
    location = None
    if latitude is not None and longitude is not None:
        location = {"lat": latitude, "lon": longitude}
    timings = [{"gte": begin, "lte": end} for begin, end in metadata.pop("timings")]
    return metadata | {
        "text": document.page_content,
        "vector": vector,
        "location": location,
        "timings": timings,
    }


def bulk_actions(
    index: str, documents: Sequence[Document], vectors: Sequence[list[float]]
) -> Iterator[dict[str, Any]]:
    """Return one bulk action per document, its id as the id of the entry."""
    for document, vector in zip(documents, vectors, strict=True):
        yield {
            "_index": index,
            "_id": document.id,
            "_source": to_source(document, vector),
        }


def indexed_uids(client: Elasticsearch, index: str, expected: int) -> set[str]:
    """Return the uids of the events with at least one entry in ``index``."""
    response = client.search(
        index=index,
        size=0,
        aggs={"uids": {"terms": {"field": "uid", "size": max(expected, 1) + 1}}},
    )
    return {bucket["key"] for bucket in response["aggregations"]["uids"]["buckets"]}


def served_indices(client: Elasticsearch, alias: str) -> list[str]:
    """Return the indices ``alias`` points at; none before the first build."""
    try:
        return sorted(client.indices.get_alias(name=alias))
    except NotFoundError:
        return []


def move_alias(client: Elasticsearch, alias: str, index: str) -> list[str]:
    """Point ``alias`` at ``index`` alone, in one atomic request; return the
    indices it pointed at before."""
    previous = [name for name in served_indices(client, alias) if name != index]
    actions: list[dict[str, Any]] = [
        {"remove": {"index": name, "alias": alias}} for name in previous
    ]
    actions.append({"add": {"index": index, "alias": alias}})
    client.indices.update_aliases(actions=actions)
    return previous


def delete_indices(client: Elasticsearch, names: Sequence[str]) -> list[str]:
    """Delete the indices ``names`` one by one; return those that are left
    after a failure."""
    left = []
    for name in names:
        try:
            client.indices.delete(index=name, ignore_unavailable=True)
        except (ApiError, TransportError):
            left.append(name)
    return left


@dataclass(frozen=True)
class IndexInfo:
    """The index an alias serves: its name, its entry count and its signature."""

    name: str
    count: int
    meta: dict[str, Any]


def served_index(client: Elasticsearch, alias: str) -> IndexInfo | None:
    """Return the index ``alias`` serves, None before the first build."""
    names = served_indices(client, alias)
    if not names:
        return None
    name = names[-1]
    mapping = client.indices.get_mapping(index=name)[name]["mappings"]
    count = client.count(index=name)["count"]
    return IndexInfo(name=name, count=count, meta=mapping.get("_meta", {}))


def signature_differences(meta: dict[str, Any], signature: dict[str, Any]) -> list[str]:
    """Return the differences between the signature of an index and
    ``signature``; none when the index is up to date."""
    return [
        f"{key}: {meta.get(key)!r} instead of {value!r}"
        for key, value in signature.items()
        if meta.get(key) != value
    ]
