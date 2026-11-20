"""Chunks within their size, cut at the most natural boundary, overlapping,
covering the whole text."""

from itertools import pairwise

from cultural_events_rag.indexing.chunking import make_splitter

SENTENCES = [
    f"Phrase numéro {i} de la description, avec un peu de contenu." for i in range(40)
]
LONG_TEXT = " ".join(SENTENCES)  # about 2,400 characters


def test_short_text_is_kept_whole() -> None:
    assert make_splitter(1000, 150)("Une description courte.") == [
        "Une description courte."
    ]


def test_empty_text_gives_no_chunk() -> None:
    assert make_splitter(1000, 150)("") == []


def test_long_text_split_within_size() -> None:
    chunks = make_splitter(chunk_size=500, chunk_overlap=100)(LONG_TEXT)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_chunks_cover_the_text_and_cut_at_sentence_ends() -> None:
    chunks = make_splitter(chunk_size=500, chunk_overlap=100)(LONG_TEXT)

    assert all(any(sentence in chunk for chunk in chunks) for sentence in SENTENCES)
    assert all(chunk.endswith(".") for chunk in chunks)


def test_lines_are_preferred_over_sentences() -> None:
    text = "Première ligne. Suite de la ligne.\nDeuxième ligne."

    assert make_splitter(chunk_size=40, chunk_overlap=0)(text) == [
        "Première ligne. Suite de la ligne.",
        "Deuxième ligne.",
    ]


def test_consecutive_chunks_overlap() -> None:
    chunks = make_splitter(chunk_size=500, chunk_overlap=100)(LONG_TEXT)

    for previous, current in pairwise(chunks):
        last_sentence = previous.rsplit(". ", 1)[-1]
        assert last_sentence in current
