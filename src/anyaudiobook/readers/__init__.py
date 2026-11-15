"""Read ebooks of every supported format into a :class:`SourceBook`.

:data:`READERS` maps file extensions to reader classes. To support another
format, subclass :class:`BookReader` (or :class:`HtmlBookReader` if the
format converts to one HTML document) and register it::

    READERS.register(Fb2Reader, *Fb2Reader.suffixes)
"""

from pathlib import Path

from anyaudiobook.models import SourceBook
from anyaudiobook.readers.base import BookReader, HtmlBookReader, HtmlSource
from anyaudiobook.readers.doc import DocReader
from anyaudiobook.readers.docx import DocxReader
from anyaudiobook.readers.epub import EpubReader
from anyaudiobook.readers.html import HtmlReader
from anyaudiobook.readers.mobi import MobiReader
from anyaudiobook.readers.pdf import PdfReader
from anyaudiobook.readers.txt import TextReader
from anyaudiobook.registry import Registry

READERS: Registry[BookReader] = Registry("input format")
"""Readers by file extension (``.epub``, ``.pdf``, ...)."""

for _reader in (
    EpubReader,
    PdfReader,
    DocxReader,
    DocReader,
    MobiReader,
    TextReader,
    HtmlReader,
):
    READERS.register(_reader, *_reader.suffixes)


def reader_for(path: str | Path) -> BookReader:
    """Return a reader for ``path``, chosen by its extension.

    Raises:
        UnsupportedFormatError: If no reader handles the extension.
    """
    return READERS.create(Path(path).suffix)


def read_source(path: str | Path, reader: BookReader | None = None) -> SourceBook:
    """Read the ebook at ``path`` with ``reader``, or the one for its extension.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnsupportedFormatError: If no reader handles the extension.
        UnreadableBookError: If the file holds no usable text.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No such ebook: {path}")
    return (reader or reader_for(path)).read(path)


__all__ = [
    "READERS",
    "BookReader",
    "DocReader",
    "DocxReader",
    "EpubReader",
    "HtmlBookReader",
    "HtmlReader",
    "HtmlSource",
    "MobiReader",
    "PdfReader",
    "TextReader",
    "read_source",
    "reader_for",
]
