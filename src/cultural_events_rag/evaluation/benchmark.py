"""The index of the benchmark: its frozen events written into Elasticsearch
under an alias of their own, by the same build as the application. It is
rebuilt only when missing, outdated, or holding other events."""

from collections.abc import Sequence

from elasticsearch import Elasticsearch
from langchain_core.embeddings import Embeddings

from cultural_events_rag.indexing.build import (
    BuildReport,
    Progress,
    build_index,
    index_signature,
)
from cultural_events_rag.indexing.store import (
    indexed_uids,
    served_index,
    signature_differences,
)
from cultural_events_rag.models import Event
from cultural_events_rag.settings import Settings

# The alias of the benchmark index.
BENCHMARK_ALIAS = "events-benchmark"


def benchmark_settings(settings: Settings, alias: str = BENCHMARK_ALIAS) -> Settings:
    """Return the settings of the application with the index alias ``alias``."""
    return settings.model_copy(update={"elasticsearch_index": alias})


def rebuild_reason(
    client: Elasticsearch,
    events: Sequence[Event],
    settings: Settings,
    alias: str = BENCHMARK_ALIAS,
) -> str | None:
    """Return why the index of ``alias`` must be built for ``events``, or None
    when it is up to date."""
    info = served_index(client, alias)
    if info is None:
        return "missing"
    differences = signature_differences(info.meta, index_signature())
    if differences:
        return f"outdated ({'; '.join(differences)})"
    uids = {event.uid for event in events}
    if indexed_uids(client, info.name, len(uids)) != uids:
        return "built on other events"
    return None


def build_benchmark_index(
    client: Elasticsearch,
    events: Sequence[Event],
    embeddings: Embeddings,
    settings: Settings,
    alias: str = BENCHMARK_ALIAS,
    on_progress: Progress | None = None,
) -> BuildReport:
    """Write ``events`` into a new index and move ``alias`` onto it."""
    return build_index(
        client, events, embeddings, benchmark_settings(settings, alias), on_progress
    )
