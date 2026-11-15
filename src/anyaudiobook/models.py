"""Data models shared across the package.

Every input format is read into the same intermediate form, a
:class:`SourceBook`: the book's :class:`BookMetadata` and its text as a list
of :class:`Document` objects, each an HTML body. Classification, filtering
and narration only ever see this form, so they work the same for every
format.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from bs4 import Tag
from pydantic import BaseModel

from anyaudiobook.markup import extract_text, heading_titles, parse_html


class BookContent(BaseModel):
    """A single chapter extracted from an ebook."""

    chapter_number: int
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class CoverImage:
    """Cover art to embed in the audio files."""

    data: bytes = field(repr=False)
    mime_type: str = "image/jpeg"
    """``image/jpeg`` or ``image/png``."""

    @classmethod
    def from_file(cls, path: str | Path) -> CoverImage:
        """Read a JPEG or PNG file; the type is judged by its extension."""
        path = Path(path)
        mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return cls(path.read_bytes(), mime_type)


@dataclass(frozen=True, slots=True)
class BookMetadata:
    """What a book is: title, authors, language and cover.

    Readers fill in what the file says about itself; values set by the user
    win, see :meth:`updated`.
    """

    title: str | None = None
    authors: tuple[str, ...] = ()
    language: str | None = None
    cover: CoverImage | None = None

    @property
    def author(self) -> str:
        """The authors joined into one string, e.g. for an ID3 artist tag."""
        return ", ".join(self.authors)

    def updated(self, overrides: BookMetadata | None) -> BookMetadata:
        """Return a copy where the fields set in ``overrides`` win."""
        if overrides is None:
            return self
        return replace(
            self,
            title=overrides.title or self.title,
            authors=overrides.authors or self.authors,
            language=overrides.language or self.language,
            cover=overrides.cover or self.cover,
        )


@dataclass(frozen=True, slots=True)
class Reference:
    """A guide or landmark entry pointing at a document."""

    type: str
    """The entry's type, e.g. ``toc``, ``copyright-page`` or ``bodymatter``."""
    partial: bool = False
    """True when the entry points at a fragment inside the document."""


@dataclass(frozen=True, slots=True)
class Document:
    """One part of a book (an EPUB spine document, a DOCX section, a range
    of PDF pages, ...), prepared for classification and narration."""

    file_name: str
    """The part's name: its path inside an EPUB, or a name made up by the
    reader such as ``section-003`` or ``pages 12-18``."""
    body: Tag
    text: str
    titles: tuple[str, ...] = ()
    """Title candidates from the document's headings and the book's TOC."""
    toc_label: str | None = None
    """The document's label in the book's table of contents."""
    linear: bool = True
    is_nav: bool = False
    references: tuple[Reference, ...] = ()

    @classmethod
    def from_html(
        cls,
        file_name: str,
        html: str | bytes,
        *,
        toc_label: str | None = None,
        linear: bool = True,
        is_nav: bool = False,
        references: tuple[Reference, ...] = (),
    ) -> Document:
        """Parse an XHTML document.

        Args:
            file_name: The document's path inside the book.
            html: The raw XHTML content.
            toc_label: The document's label in the book's table of contents.
            linear: False when the spine marks the document ``linear="no"``.
            is_nav: True for the EPUB 3 navigation document.
            references: Guide and landmark entries pointing at the document.

        Returns:
            The parsed document.
        """
        return cls.from_body(
            file_name,
            parse_html(html),
            toc_label=toc_label,
            linear=linear,
            is_nav=is_nav,
            references=references,
        )

    @classmethod
    def from_body(
        cls,
        file_name: str,
        body: Tag,
        *,
        toc_label: str | None = None,
        linear: bool = True,
        is_nav: bool = False,
        references: tuple[Reference, ...] = (),
    ) -> Document:
        """Wrap an already parsed HTML body, see :meth:`from_html`."""
        titles = heading_titles(body)
        if toc_label:
            titles.append(toc_label)
        return cls(
            file_name=file_name,
            body=body,
            text=extract_text(body),
            titles=tuple(dict.fromkeys(titles)),
            toc_label=toc_label,
            linear=linear,
            is_nav=is_nav,
            references=references,
        )

    @property
    def word_count(self) -> int:
        """The number of words in the document's text."""
        return len(self.text.split())


@dataclass(frozen=True, slots=True)
class SourceBook:
    """A book as read from its file, before anything is filtered out."""

    documents: list[Document]
    """The book's parts in reading order."""
    metadata: BookMetadata = field(default_factory=BookMetadata)
