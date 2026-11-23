"""The splitting of a long description into chunks. Any ``TextSplitter`` can
replace the default one."""

from collections.abc import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

TextSplitter = Callable[[str], list[str]]

# Chunks of up to CHUNK_SIZE characters, each repeating the last CHUNK_OVERLAP
# characters of the previous one.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Boundaries tried in order: lines, sentences, words.
SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


def make_splitter(chunk_size: int, chunk_overlap: int) -> TextSplitter:
    """Return a recursive splitter: chunks of up to ``chunk_size`` characters,
    cut at the first boundary that fits, each repeating at most the last
    ``chunk_overlap`` characters of the previous one."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        keep_separator="end",  # punctuation stays with its sentence
    )
    return splitter.split_text
