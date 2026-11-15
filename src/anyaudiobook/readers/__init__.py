"""Read ebooks of every supported format into a :class:`SourceBook`.

To support another format, write a :class:`BookReader` (or an
:class:`HtmlBookReader` if the format converts to one HTML document) and add
it to :data:`READERS`.
"""

from pathlib import Path

from anyaudiobook.errors import UnsupportedFormatError
from anyaudiobook.models import SourceBook
from anyaudiobook.readers.base import BookReader
from anyaudiobook.readers.doc import DocReader
from anyaudiobook.readers.docx import DocxReader
from anyaudiobook.readers.epub import EpubReader
from anyaudiobook.readers.html import HtmlReader
from anyaudiobook.readers.mobi import MobiReader
from anyaudiobook.readers.pdf import PdfReader
from anyaudiobook.readers.txt import TextReader

READERS: dict[str, type[BookReader]] = {
    suffix: reader
    for reader in (
        EpubReader,
        PdfReader,
        DocxReader,
        DocReader,
        MobiReader,
        TextReader,
        HtmlReader,
    )
    for suffix in reader.suffixes
}
"""Readers by lowercase file extension (``.epub``, ``.pdf``, ...)."""


def reader_for(path: str | Path) -> BookReader:
    """Return a reader for ``path``, chosen by its extension.

    Raises:
        UnsupportedFormatError: If no reader handles the extension.
    """
    suffix = Path(path).suffix
    reader = READERS.get(suffix.lower())
    if reader is None:
        raise UnsupportedFormatError(
            f"Unsupported input format {suffix!r}; supported: {', '.join(sorted(READERS))}"
        )
    return reader()


def read_source(path: str | Path) -> SourceBook:
    """Read the ebook at ``path`` with the reader for its extension.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnsupportedFormatError: If no reader handles the extension.
        UnreadableBookError: If the file holds no usable text.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No such ebook: {path}")
    return reader_for(path).read(path)
