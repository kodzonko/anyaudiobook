"""Package narrated chapters as audiobooks of every supported format.

To add a format, write an :class:`AudiobookWriter` and add it to
:data:`WRITERS`.
"""

from anyaudiobook.errors import UnsupportedFormatError
from anyaudiobook.writers.base import AudiobookWriter
from anyaudiobook.writers.m4b import M4bWriter
from anyaudiobook.writers.mp3 import Mp3Writer

WRITERS: dict[str, type[AudiobookWriter]] = {
    writer.format_name: writer for writer in (Mp3Writer, M4bWriter)
}
"""Writers by format name (``mp3``, ``m4b``)."""


def writer_for(format_name: str) -> AudiobookWriter:
    """Return a writer for ``format_name`` (``mp3``, ``m4b``, ``.m4b``...).

    Raises:
        UnsupportedFormatError: If no writer handles the format.
    """
    name = format_name.lstrip(".")
    writer = WRITERS.get(name.lower())
    if writer is None:
        raise UnsupportedFormatError(
            f"Unsupported output format {name!r}; supported: {', '.join(sorted(WRITERS))}"
        )
    return writer()
