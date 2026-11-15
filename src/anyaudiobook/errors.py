"""Exceptions raised by anyaudiobook."""


class AnyAudiobookError(Exception):
    """Base class of every error this package raises on purpose."""


class UnsupportedFormatError(AnyAudiobookError, ValueError):
    """No reader or writer is registered for the requested format."""


class UnreadableBookError(AnyAudiobookError):
    """The book cannot be read, e.g. a scanned PDF or a DRM-protected file."""


class MissingToolError(AnyAudiobookError):
    """An external program needed for the job is not installed."""
