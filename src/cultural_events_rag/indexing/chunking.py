"""How a long description is split into chunks. Knows nothing about events or
documents: any ``TextSplitter``, a function from a text to its chunks, can take
its place, to compare chunking strategies.
"""

from collections.abc import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

TextSplitter = Callable[[str], list[str]]

# The chunks of the index: up to CHUNK_SIZE characters, the last CHUNK_OVERLAP
# of a chunk repeated at the start of the next. Most descriptions fit in one.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# The natural boundaries first: lines (the paragraphs of the HTML), then
# sentences, then words.
SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


def make_splitter(chunk_size: int, chunk_overlap: int) -> TextSplitter:
    """A recursive splitter: chunks of up to ``chunk_size`` characters, cut at the
    most natural boundary that fits, each repeating the last ``chunk_overlap``
    characters of the previous one at most."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        keep_separator="end",  # punctuation stays at the end of its sentence
    )
    return splitter.split_text
