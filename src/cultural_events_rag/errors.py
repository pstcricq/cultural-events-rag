"""Every error this package raises."""


class SourceError(RuntimeError):
    """A call to a source of events failed for good: retries spent, or an
    error not worth retrying."""


class MissingSettingError(RuntimeError):
    """A setting the command needs, a key or a password, is not set."""
