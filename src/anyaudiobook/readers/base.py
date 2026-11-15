"""The reader interface and the shared template for HTML-based formats."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from bs4 import BeautifulSoup, Tag

from anyaudiobook.markup import clean_body
from anyaudiobook.models import BookMetadata, Document, SourceBook
from anyaudiobook.readers.headings import class_font_sizes
from anyaudiobook.readers.splitting import mark_toc, relink, split_sections


class BookReader(ABC):
    """Turns files of one ebook format into a :class:`SourceBook`.

    Each format gets a subclass; :data:`anyaudiobook.readers.READERS` picks
    one by file extension. Everything after reading (classification,
    filtering, narration) is shared, so a reader only has to produce
    :class:`Document` objects: HTML bodies in reading order.
    """

    suffixes: ClassVar[tuple[str, ...]] = ()
    """File extensions the reader handles, e.g. ``(".epub",)``."""

    @abstractmethod
    def read(self, path: Path) -> SourceBook:
        """Read the book at ``path``.

        Raises:
            UnreadableBookError: If the file holds no usable text.
        """


@dataclass(frozen=True, slots=True)
class HtmlSource:
    """A whole book loaded as one HTML document."""

    html: str | bytes
    metadata: BookMetadata = field(default_factory=BookMetadata)
    """What the file says about the book; wins over the HTML ``<head>``."""
    toc: Mapping[str, str] = field(default_factory=dict)
    """A table of contents kept outside the HTML: element id → entry label."""


class HtmlBookReader(BookReader):
    """Template for formats that load as one long HTML document.

    :meth:`read` runs the shared steps: parse, read the ``<head>``
    metadata, find headings when the document has none, split into sections (see
    :mod:`anyaudiobook.readers.splitting`) and fix links between them.
    Subclasses only implement :meth:`load`, and may refine :meth:`prepare`
    and :meth:`section_name`.
    """

    def read(self, path: Path) -> SourceBook:
        """Load the book and split it into documents."""
        source = self.load(Path(path))
        soup = BeautifulSoup(source.html, "html.parser")
        metadata = head_metadata(soup).updated(source.metadata)
        class_sizes = class_font_sizes(soup)
        body = clean_body(soup)
        mark_toc(body, source.toc)
        self.prepare(body)
        sections = split_sections(body, class_sizes)
        named = [
            (self.section_name(index, section.body), section)
            for index, section in enumerate(sections, start=1)
        ]
        relink([(name, section.body) for name, section in named])
        documents = [
            Document.from_body(name, section.body, toc_label=section.label)
            for name, section in named
        ]
        return SourceBook(documents=documents, metadata=metadata)

    @abstractmethod
    def load(self, path: Path) -> HtmlSource:
        """Return the book as one HTML document, with its metadata."""

    def prepare(self, body: Tag) -> None:
        """Adjust the parsed body before it is split; does nothing by default."""

    def section_name(self, index: int, body: Tag) -> str:
        """Return the name of the ``index``-th section (1-based)."""
        return f"section-{index:03d}"


_AUTHOR_META = frozenset({"author", "creator", "dc.creator", "dcterms.creator"})


def head_metadata(soup: BeautifulSoup) -> BookMetadata:
    """Read the title, author and language from an HTML document's head."""
    title = soup.find("title")
    authors = tuple(
        content.strip()
        for meta in soup.find_all("meta")
        if isinstance(meta, Tag)
        and str(meta.get("name", "")).lower() in _AUTHOR_META
        and isinstance(content := meta.get("content"), str)
        and content.strip()
    )
    root = soup.find("html")
    language = root.get("lang") if isinstance(root, Tag) else None
    return BookMetadata(
        title=title.get_text(strip=True) or None if isinstance(title, Tag) else None,
        authors=tuple(dict.fromkeys(authors)),
        language=language.strip() or None if isinstance(language, str) else None,
    )
