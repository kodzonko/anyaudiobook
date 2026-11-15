"""Read Kindle books (MOBI, AZW, AZW3) by unpacking them."""

import shutil
from pathlib import Path

import mobi
from bs4 import BeautifulSoup, Tag

from anyaudiobook.errors import UnreadableBookError
from anyaudiobook.models import BookMetadata, CoverImage, SourceBook
from anyaudiobook.readers.base import BookReader, HtmlBookReader, HtmlSource
from anyaudiobook.readers.epub import EpubReader
from anyaudiobook.readers.pdf import PdfReader
from anyaudiobook.readers.splitting import toc_depth

_COVER_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class MobiReader(BookReader):
    """Reads DRM-free Kindle books.

    The ``mobi`` package (KindleUnpack) unpacks the file. KF8 books (AZW3
    and most modern MOBI files) unpack to an EPUB, read by
    :class:`EpubReader`; print replicas to a PDF, read by
    :class:`PdfReader`; old MOBI 7 books to one HTML file with a separate
    table of contents, read by :class:`Mobi7Reader`.
    """

    suffixes = (".mobi", ".azw", ".azw3", ".kf8", ".prc")

    def read(self, path: Path) -> SourceBook:
        """Unpack the book and read what it contains.

        Raises:
            UnreadableBookError: If the file cannot be unpacked, for example
                because it is protected by DRM.
        """
        try:
            scratch, extracted = mobi.extract(str(path))
        except Exception as error:  # KindleUnpack raises bare Exceptions
            raise UnreadableBookError(
                f"Cannot unpack {path} (is it protected by DRM?): {error}"
            ) from error
        try:
            unpacked = Path(extracted)
            match unpacked.suffix.lower():
                case ".epub":
                    return EpubReader().read(unpacked)
                case ".pdf":
                    return PdfReader().read(unpacked)
                case _:
                    return Mobi7Reader().read(unpacked)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


class Mobi7Reader(HtmlBookReader):
    """Reads an unpacked MOBI 7 book: ``book.html`` with ``toc.ncx`` and
    ``content.opf`` beside it.

    Chapters start where the NCX table of contents points; without one, at
    headings or ``<mbp:pagebreak>``.
    """

    suffixes = ()

    def load(self, path: Path) -> HtmlSource:
        """Read the HTML, its table of contents and its metadata."""
        ncx = path.with_name("toc.ncx")
        opf = path.with_name("content.opf")
        return HtmlSource(
            path.read_bytes(),
            metadata=opf_metadata(opf) if opf.is_file() else BookMetadata(),
            toc=ncx_anchors(ncx, path.name) if ncx.is_file() else {},
        )


def ncx_anchors(ncx: Path, html_name: str) -> dict[str, str]:
    """Map the anchors an NCX table of contents points at to their labels.

    Only entries down to :func:`toc_depth` are used, so a book whose NCX
    nests sections under chapters is split by chapter.

    Args:
        ncx: The ``toc.ncx`` file.
        html_name: Name of the HTML file the entries point into.
    """
    soup = BeautifulSoup(ncx.read_bytes(), "xml")
    entries: list[tuple[int, str, str]] = []
    for point in soup.find_all("navPoint"):
        if not isinstance(point, Tag):
            continue
        label = point.find("text")
        content = point.find("content")
        source = content.get("src") if isinstance(content, Tag) else None
        if not isinstance(label, Tag) or not isinstance(source, str):
            continue
        file_name, _, fragment = source.partition("#")
        if fragment and file_name in ("", html_name):
            level = len(point.find_parents("navPoint")) + 1
            entries.append((level, fragment, " ".join(label.get_text().split())))
    depth = toc_depth([level for level, _, _ in entries])
    anchors: dict[str, str] = {}
    for level, fragment, label in entries:
        if level <= depth and label:
            anchors.setdefault(fragment, label)
    return anchors


def opf_metadata(opf: Path) -> BookMetadata:
    """Read the title, authors, language and cover from an OPF package file."""
    soup = BeautifulSoup(opf.read_bytes(), "xml")

    def texts(name: str) -> list[str]:
        """Return the non-empty texts of every ``name`` element."""
        return [
            text
            for element in soup.find_all(name)
            if (text := " ".join(element.get_text().split()))
        ]

    titles, languages = texts("dc:title"), texts("dc:language")
    return BookMetadata(
        title=titles[0] if titles else None,
        authors=tuple(dict.fromkeys(texts("dc:creator"))),
        language=languages[0] if languages else None,
        cover=_opf_cover(soup, opf.parent),
    )


def _opf_cover(soup: BeautifulSoup, root: Path) -> CoverImage | None:
    """Return the cover image an OPF file's ``<meta name="cover">`` names."""
    meta = soup.find("meta", attrs={"name": "cover"})
    identifier = meta.get("content") if isinstance(meta, Tag) else None
    item = soup.find("item", id=identifier) if isinstance(identifier, str) else None
    href = item.get("href") if isinstance(item, Tag) else None
    if not isinstance(href, str):
        return None
    image = root / href
    mime_type = _COVER_TYPES.get(image.suffix.lower())
    if mime_type is None or not image.is_file():
        return None
    return CoverImage(image.read_bytes(), mime_type)
