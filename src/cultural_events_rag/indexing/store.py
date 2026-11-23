"""The index of the events in Elasticsearch: one entry per document, its French
text for the lexical search (BM25) and its vector for the vector search (kNN)
side by side, with the metadata the search filters on.

Each build writes a new index, named after the alias and its build time, then
moves the alias onto it once complete: the alias always serves a whole index,
and a failed build never touches it. The signature of a build, what it was made
with, lives in the ``_meta`` of its index.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from elasticsearch import ApiError, Elasticsearch, NotFoundError, TransportError
from langchain_core.documents import Document

# One shard, no replica: one node, a few thousand documents. The folded
# analyzer cuts a name into words, in lower case, without accents nor elisions
# (l', d'): "Chapelle des Carmélites" is found by "carmelites".
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

# The version of the fields below, in the signature of each index: raised at
# each change of them, so that status reports an index built with the former.
MAPPING_VERSION = 1

# The vector search is exact: the question compared with every vector, by
# cosine. At a few thousand documents it is instant, and finds the true nearest
# neighbors; an approximate graph (hnsw) only pays off at hundreds of thousands.
VECTOR_INDEX = "flat"


def index_mappings(dims: int, signature: dict[str, Any]) -> dict[str, Any]:
    """The fields of an index whose vectors have ``dims`` dimensions; any other
    field is refused."""
    keyword = {"type": "keyword"}
    stored = {"type": "keyword", "index": False}  # returned, never searched
    folded = {"type": "text", "analyzer": "folded"}
    return {
        "_meta": signature,
        "dynamic": "strict",
        "properties": {
            # The French analyzer: elisions (l', d'), stop words, light stemming.
            "text": {"type": "text", "analyzer": "french"},
            # The whole event, the same in each of its chunks: what the LLM
            # reads, never searched.
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
            # Each slot as a range: a period matches the events with a slot in it.
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
    """The name of the index a build at ``now`` writes, behind ``alias``."""
    return f"{alias}-{now:%Y%m%d-%H%M%S}"


def to_source(document: Document, vector: list[float]) -> dict[str, Any]:
    """What the index stores of a document: its text, its vector and its
    metadata, the coordinates as a point and each slot as a date range."""
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
    """One bulk action per document, its id kept as the id of the entry."""
    for document, vector in zip(documents, vectors, strict=True):
        yield {
            "_index": index,
            "_id": document.id,
            "_source": to_source(document, vector),
        }


def indexed_uids(client: Elasticsearch, index: str, expected: int) -> set[str]:
    """The uids of the events with at least one entry in ``index``."""
    response = client.search(
        index=index,
        size=0,
        aggs={"uids": {"terms": {"field": "uid", "size": max(expected, 1) + 1}}},
    )
    return {bucket["key"] for bucket in response["aggregations"]["uids"]["buckets"]}


def served_indices(client: Elasticsearch, alias: str) -> list[str]:
    """The indices ``alias`` points at: none before the first build."""
    try:
        return sorted(client.indices.get_alias(name=alias))
    except NotFoundError:
        return []


def move_alias(client: Elasticsearch, alias: str, index: str) -> list[str]:
    """Point ``alias`` at ``index`` alone, in one atomic step: the names of the
    indices it served before."""
    previous = [name for name in served_indices(client, alias) if name != index]
    actions: list[dict[str, Any]] = [
        {"remove": {"index": name, "alias": alias}} for name in previous
    ]
    actions.append({"add": {"index": index, "alias": alias}})
    client.indices.update_aliases(actions=actions)
    return previous


def delete_indices(client: Elasticsearch, names: Sequence[str]) -> list[str]:
    """Delete the indices ``names``, each on its own: the names of those still
    there after a failure."""
    left = []
    for name in names:
        try:
            client.indices.delete(index=name, ignore_unavailable=True)
        except (ApiError, TransportError):
            left.append(name)
    return left


@dataclass(frozen=True)
class IndexInfo:
    """The index an alias serves: its name, its entries and its signature."""

    name: str
    count: int
    meta: dict[str, Any]


def served_index(client: Elasticsearch, alias: str) -> IndexInfo | None:
    """The index ``alias`` serves, None before the first build."""
    names = served_indices(client, alias)
    if not names:
        return None
    name = names[-1]
    mapping = client.indices.get_mapping(index=name)[name]["mappings"]
    count = client.count(index=name)["count"]
    return IndexInfo(name=name, count=count, meta=mapping.get("_meta", {}))


def signature_differences(meta: dict[str, Any], signature: dict[str, Any]) -> list[str]:
    """What differs between the signature an index was built with and
    ``signature``: nothing when the index is up to date."""
    return [
        f"{key}: {meta.get(key)!r} instead of {value!r}"
        for key, value in signature.items()
        if meta.get(key) != value
    ]
