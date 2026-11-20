"""The ``cultural-events-rag documents`` command: the documents the events make,
as the index will store them."""

import argparse
import json
import sys
from collections import Counter

from cultural_events_rag.cli.output import shown
from cultural_events_rag.collection.files import load_events
from cultural_events_rag.indexing.chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    make_splitter,
)
from cultural_events_rag.indexing.documents import events_to_documents
from cultural_events_rag.paths import EVENTS_FILE


def _documents(args: argparse.Namespace) -> int:
    if not EVENTS_FILE.is_file():
        print(
            f"FAIL no events in {shown(EVENTS_FILE)}: run make process", file=sys.stderr
        )
        return 1

    events = load_events(EVENTS_FILE)
    if args.uid:
        events = [event for event in events if event.uid == args.uid]
        if not events:
            print(f"FAIL no event {args.uid} in {shown(EVENTS_FILE)}", file=sys.stderr)
            return 1
    split = make_splitter(CHUNK_SIZE, CHUNK_OVERLAP)
    documents = events_to_documents(events, split)

    if args.uid:
        for document in documents:
            print(f"--- {document.id}\n\n{document.page_content}\n")
            print(json.dumps(document.metadata, ensure_ascii=False, indent=2), "\n")
        return 0

    if not documents:
        print(f"Documents: 0, no event in {shown(EVENTS_FILE)}")
        return 0
    chunks = Counter(document.metadata["uid"] for document in documents)
    lengths = [len(document.page_content) for document in documents]
    print(
        f"Events: {len(events)} <- {shown(EVENTS_FILE)}, "
        f"chunks: {CHUNK_SIZE} chars, {CHUNK_OVERLAP} overlap\n"
    )
    print(f"Documents: {len(documents)}")
    print(
        f"Events split: {sum(n > 1 for n in chunks.values())} (most: {max(chunks.values())})"
    )
    print(
        f"Characters per document: {sum(lengths) // len(lengths)} on average, "
        f"{max(lengths)} at most"
    )
    print(f"Characters in all: {sum(lengths)}")
    return 0


def add_commands(commands: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add ``cultural-events-rag documents`` to the cultural-events-rag command."""
    documents = commands.add_parser(
        "documents", help="the documents the events make, as the index will store them"
    )
    documents.add_argument("--uid", help="print every document of this event")
    documents.set_defaults(run=_documents)
