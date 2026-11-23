"""The errors raised by the package."""


class SourceError(RuntimeError):
    """A call to a source of events failed after its retries, or with an error
    that is not retried."""


class MissingSettingError(RuntimeError):
    """A setting the command needs is not set."""


class IncompleteIndexError(RuntimeError):
    """Some events have no document in the new index; the alias is not moved."""


class RerankerError(RuntimeError):
    """The reranker cannot run: the ``rerank`` extra is not installed."""


class JudgeError(RuntimeError):
    """The judge cannot run: the ``eval`` extra is not installed."""


class GenerationError(RuntimeError):
    """The chat model gave no usable answer."""


class MissingModelError(RuntimeError):
    """A Hugging Face model is not in the local cache. Every command but
    ``models`` runs offline."""
