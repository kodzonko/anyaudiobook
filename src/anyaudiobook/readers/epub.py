"""Read EPUB files, documents in spine order with their TOC labels."""

import re
import warnings
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from anyaudiobook.errors import UnreadableBookError
from anyaudiobook.markup import resolve_href, semantic_types
from anyaudiobook.models import (
    BookMetadata,
    CoverImage,
    Document,
    Reference,
    SourceBook,
)
from anyaudiobook.readers.base import BookReader

# Silence noisy ebooklib warnings that don't affect parsing.
warnings.filterwarnings(
    "ignore",
    message="In the future version we will turn default option ignore_ncx to True.",
)
warnings.filterwarnings(
    "ignore",
    message="This search incorrectly ignores the root element, and will be fixed in a future version.",
)


_COVER_TYPES = frozenset({"image/jpeg", "image/png"})
_CIPHER_URI = re.compile(r"CipherReference[^>]*\bURI\s*=\s*[\"']([^\"']+)")
_ENCRYPTED_TEXT = re.compile(r"\.(?:x?html?|xml|opf|ncx)$", re.IGNORECASE)


class EpubReader(BookReader):
    """Reads EPUB 2 and 3 files with ebooklib.

    Every spine document becomes a :class:`Document`, with its label in the
    table of contents, the guide and landmark entries pointing at it and
    its ``linear`` flag, which the classifier all uses.
    """

    suffixes = (".epub",)

    def read(self, path: Path) -> SourceBook:
        """Read the book's documents in reading order and its metadata.

        Raises:
            UnreadableBookError: If the file is not a valid EPUB or is
                protected by DRM.
        """
        try:
            if is_drm_protected(path):
                raise UnreadableBookError(f"{path} is protected by DRM")
            book = epub.read_epub(str(path))
        except (epub.EpubException, zipfile.BadZipFile, KeyError, OSError) as error:
            raise UnreadableBookError(f"Cannot read EPUB {path}: {error}") from error
        return SourceBook(documents=load_documents(book), metadata=read_metadata(book))


def read_metadata(book: epub.EpubBook) -> BookMetadata:
    """Return the title, authors, language and cover image of an EPUB."""

    def first(name: str) -> str | None:
        """Return the first non-empty value of a Dublin Core element."""
        values = (value.strip() for value, _ in book.get_metadata("DC", name) if value)
        return next((value for value in values if value), None)

    authors = tuple(
        value.strip()
        for value, _ in book.get_metadata("DC", "creator")
        if value and value.strip()
    )
    return BookMetadata(
        title=first("title"),
        authors=authors,
        language=first("language"),
        cover=_cover(book),
    )


def is_drm_protected(path: Path) -> bool:
    """Return True if the EPUB's text documents are encrypted.

    ``META-INF/encryption.xml`` alone is no proof: publishers also use it to
    obfuscate embedded fonts, which does not stop the text being read.
    """
    with zipfile.ZipFile(path) as archive:
        try:
            manifest = archive.read("META-INF/encryption.xml").decode(
                "utf-8", "replace"
            )
        except KeyError:
            return False
    return any(_ENCRYPTED_TEXT.search(uri) for uri in _CIPHER_URI.findall(manifest))


def _cover(book: epub.EpubBook) -> CoverImage | None:
    """Return the book's cover image, from EPUB 3 or EPUB 2 metadata."""
    candidates = list(book.get_items_of_type(ebooklib.ITEM_COVER))
    for _, attributes in book.get_metadata("OPF", "meta"):
        if attributes.get("name") == "cover" and (
            item := book.get_item_with_id(attributes.get("content", ""))
        ):
            candidates.append(item)
    for item in candidates:
        if item.media_type in _COVER_TYPES and isinstance(item.content, bytes):
            return CoverImage(item.content, item.media_type)
    return None


def load_documents(book: epub.EpubBook) -> list[Document]:
    """Prepare a book's spine documents for classification.

    Args:
        book: The book, as read by ebooklib.

    Returns:
        The documents in reading order, with their TOC labels, guide and
        landmark entries and ``linear`` flags.
    """
    order = _reading_order(book)
    file_names = {item.get_name() for item, _ in order}
    references = _references(book)
    labels = _toc_labels(book, file_names)
    return [
        Document.from_html(
            item.get_name(),
            # Raw content: ``get_content()`` rebuilds the page and drops the
            # attributes of <body>, where ``epub:type`` often is.
            item.content,
            toc_label=labels.get(item.get_name()),
            linear=linear,
            is_nav=isinstance(item, epub.EpubNav),
            references=tuple(references.get(item.get_name(), ())),
        )
        for item, linear in order
    ]


def _reading_order(book: epub.EpubBook) -> list[tuple[epub.EpubItem, bool]]:
    """Return the book's documents in spine order with their ``linear`` flag.

    Falls back to manifest order when the spine lists no documents.
    """
    order: list[tuple[epub.EpubItem, bool]] = []
    for entry in book.spine:
        idref, *rest = entry if isinstance(entry, tuple) else (entry,)
        item = book.get_item_with_id(idref) if isinstance(idref, str) else idref
        if (
            isinstance(item, epub.EpubItem)
            and item.get_type() == ebooklib.ITEM_DOCUMENT
        ):
            order.append((item, not rest or rest[0] != "no"))
    if order:
        return order
    return [(item, True) for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]


def _references(book: epub.EpubBook) -> dict[str, list[Reference]]:
    """Collect EPUB 2 guide and EPUB 3 landmark entries by target document."""
    references: defaultdict[str, list[Reference]] = defaultdict(list)
    for entry in book.guide:
        href, kind = entry.get("href"), entry.get("type")
        if isinstance(href, str) and href and isinstance(kind, str) and kind:
            name, fragment = resolve_href("", href)
            references[name].append(Reference(kind.lower(), partial=bool(fragment)))

    for item in book.get_items():
        if not isinstance(item, epub.EpubNav):
            continue
        soup = BeautifulSoup(item.content, "html.parser")
        for nav in soup.find_all("nav"):
            if not isinstance(nav, Tag) or "landmarks" not in semantic_types(nav):
                continue
            for link in nav.find_all("a", href=True):
                href = link.get("href") if isinstance(link, Tag) else None
                if not isinstance(link, Tag) or not isinstance(href, str):
                    continue
                name, fragment = resolve_href(item.get_name(), href)
                for kind in semantic_types(link):
                    references[name].append(Reference(kind, partial=bool(fragment)))
    return references


def _toc_labels(book: epub.EpubBook, file_names: set[str]) -> dict[str, str]:
    """Map document names to their label in the book's table of contents.

    A label for the whole document wins over one for a fragment of it.
    """
    # NCX links are relative to the NCX file, nav links to the OPF directory.
    bases = [""] + [
        ncx.get_name() for ncx in book.get_items_of_type(ebooklib.ITEM_NAVIGATION)
    ]
    labels: dict[str, str] = {}
    whole: set[str] = set()
    for href, label in _walk_toc(book.toc):
        for base in bases:
            name, fragment = resolve_href(base, href)
            if name in file_names:
                break
        else:
            continue
        if name not in labels or (not fragment and name not in whole):
            labels[name] = label
        if not fragment:
            whole.add(name)
    return labels


def _walk_toc(entries: Iterable[object]) -> Iterator[tuple[str, str]]:
    """Yield ``(href, label)`` for every entry of an ebooklib TOC tree."""
    for entry in entries:
        if isinstance(entry, tuple | list):
            yield from _walk_toc(
                child
                for part in entry
                for child in (part if isinstance(part, list) else [part])
            )
        elif isinstance(entry, epub.Link | epub.Section):
            if entry.href and entry.title:
                yield entry.href, entry.title.strip()
        elif isinstance(entry, epub.EpubHtml) and entry.title:
            yield entry.file_name, entry.title.strip()
