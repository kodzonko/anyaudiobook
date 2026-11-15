"""Read Word (DOCX) documents with mammoth."""

import re
import zipfile
from pathlib import Path

import mammoth
from bs4 import BeautifulSoup, Tag

from anyaudiobook.errors import UnreadableBookError
from anyaudiobook.models import BookMetadata
from anyaudiobook.readers.base import HtmlBookReader, HtmlSource

STYLE_MAP = """
p[style-name='Title'] => h1:fresh
p[style-name='Subtitle'] => h2:fresh
"""
"""Mammoth style map additions: Word's Title style starts a title page."""

_NOTE_ID = re.compile(r"^(?:footnote|endnote)-\d+$")


class DocxReader(HtmlBookReader):
    """Reads DOCX files: headings from Word's heading styles, or from
    chapter-like paragraphs when the document uses none.

    Footnotes and endnotes, which mammoth collects at the end of the
    document, become a notes section of their own; note markers in the text
    are removed with the rest of the note clean-up.
    """

    suffixes = (".docx",)

    def load(self, path: Path) -> HtmlSource:
        """Convert the document to HTML.

        Raises:
            UnreadableBookError: If the file is not a valid DOCX.
        """
        try:
            with path.open("rb") as file:
                result = mammoth.convert_to_html(
                    file,
                    style_map=STYLE_MAP,
                    convert_image=mammoth.images.img_element(lambda _: {"src": ""}),
                )
            metadata = docx_metadata(path)
        except (zipfile.BadZipFile, KeyError) as error:
            raise UnreadableBookError(f"Cannot read DOCX {path}: {error}") from error
        return HtmlSource(result.value, metadata)

    def prepare(self, body: Tag) -> None:
        """Mark mammoth's lists of footnotes and endnotes as notes."""
        for item in body.find_all("li", id=_NOTE_ID):
            if isinstance(item, Tag) and isinstance(item.parent, Tag):
                item.parent["role"] = "doc-endnotes"


def docx_metadata(path: Path) -> BookMetadata:
    """Read the title, author and language from ``docProps/core.xml``."""
    with zipfile.ZipFile(path) as archive:
        try:
            core = archive.read("docProps/core.xml")
        except KeyError:
            return BookMetadata()
    soup = BeautifulSoup(core, "xml")

    def value(name: str) -> str | None:
        """Return the text of a core property, if set."""
        element = soup.find(name)
        return element.get_text(strip=True) or None if element else None

    creator = value("dc:creator")
    return BookMetadata(
        title=value("dc:title"),
        authors=tuple(
            name.strip() for name in (creator or "").split(";") if name.strip()
        ),
        language=value("dc:language"),
    )
