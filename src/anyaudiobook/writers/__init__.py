"""Package narrated chapters as audiobooks of every supported format.

:data:`WRITERS` maps format names to writer classes. To add a format,
subclass :class:`AudiobookWriter` and register it::

    WRITERS.register(OpusWriter, OpusWriter.format_name)
"""

from anyaudiobook.registry import Registry
from anyaudiobook.writers.base import AudiobookWriter, Track
from anyaudiobook.writers.m4b import M4bWriter
from anyaudiobook.writers.mp3 import Mp3Writer

WRITERS: Registry[AudiobookWriter] = Registry("output format")
"""Writers by format name (``mp3``, ``m4b``)."""

for _writer in (Mp3Writer, M4bWriter):
    WRITERS.register(_writer, _writer.format_name)


def writer_for(format_name: str) -> AudiobookWriter:
    """Return a writer for ``format_name`` (``mp3``, ``m4b``...).

    Raises:
        UnsupportedFormatError: If no writer is registered under the name.
    """
    return WRITERS.create(format_name.lstrip("."))


__all__ = [
    "WRITERS",
    "AudiobookWriter",
    "M4bWriter",
    "Mp3Writer",
    "Track",
    "writer_for",
]
