"""Every error this package raises."""


class SourceError(RuntimeError):
    """A call to a source of events failed for good: retries spent, or an
    error not worth retrying."""


class MissingSettingError(RuntimeError):
    """A setting the command needs, a key or a password, is not set."""


class IncompleteIndexError(RuntimeError):
    """Some events have no document in the index just built: the alias stays
    on the index it served."""


class MissingModelError(RuntimeError):
    """A model of Hugging Face run on this machine is not downloaded: every
    command but ``models`` runs offline."""
