"""Data types for telling a book's main text apart from front and back matter."""

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from enum import StrEnum

from bs4 import Tag

from anyaudiobook.markup import extract_text, heading_titles, parse_html


class MatterKind(StrEnum):
    """What a document of a book is, as far as narration is concerned."""

    BODY = "body"
    """Main text: chapters, prologue, foreword, epilogue, afterword."""
    EMPTY = "empty"
    """No text at all, e.g. a cover image. Never narrated."""
    COVER = "cover"
    TITLE_PAGE = "title-page"
    TOC = "toc"
    """Table of contents and other navigation."""
    COPYRIGHT = "copyright"
    """Copyright page, imprint, colophon and credits."""
    DEDICATION = "dedication"
    EPIGRAPH = "epigraph"
    EDITORIAL_NOTE = "editorial-note"
    """Publisher's, editor's or translator's note."""
    ACKNOWLEDGMENTS = "acknowledgments"
    NOTES = "notes"
    """Footnotes and endnotes collected in a document of their own."""
    INDEX = "index"
    BIBLIOGRAPHY = "bibliography"
    """Bibliography, sources, references and further reading."""
    GLOSSARY = "glossary"
    """Glossary and lists of abbreviations."""
    LIST_OF_FIGURES = "list-of-figures"
    """Lists of illustrations, maps and tables, and picture credits."""
    REFERENCE = "reference"
    """Family trees, chronologies, maps and lists of characters."""
    ABOUT_AUTHOR = "about-author"
    ADVERTISEMENT = "advertisement"
    """"Also by", praise, previews of other books, newsletters."""
    SHORT_PAGE = "short-page"
    """A very short page before or after the main text, e.g. a half-title."""
    UNLISTED = "unlisted"
    """A page before the main text that the table of contents leaves out,
    e.g. a half-title, epigraph or praise for the book."""
    AUXILIARY = "auxiliary"
    """A document the spine marks as outside the reading order."""


DEFAULT_SKIP: frozenset[MatterKind] = frozenset(MatterKind) - {MatterKind.BODY}
"""Kinds of document that are not narrated unless configured otherwise."""


@dataclass(frozen=True, slots=True)
class Verdict:
    """The classifier's opinion of one document."""

    kind: MatterKind
    reason: str


@dataclass(frozen=True, slots=True)
class Reference:
    """A guide or landmark entry pointing at a document."""

    type: str
    """The entry's type, e.g. ``toc``, ``copyright-page`` or ``bodymatter``."""
    partial: bool = False
    """True when the entry points at a fragment inside the document."""


@dataclass(frozen=True, slots=True)
class Document:
    """One document of a book's spine, prepared for classification."""

    file_name: str
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
        body = parse_html(html)
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
class FilterOptions:
    """Settings deciding which documents of a book are narrated.

    Patterns are regular expressions searched, ignoring case, in each
    document's file name and title. ``exclude`` wins over ``include``, and
    both win over the classifier. Empty documents are never narrated.
    """

    skip: AbstractSet[MatterKind] = DEFAULT_SKIP
    """Kinds of document not to narrate."""
    include: tuple[str, ...] = ()
    """Patterns of documents to narrate whatever their kind."""
    exclude: tuple[str, ...] = ()
    """Patterns of documents never to narrate."""
    short_page_words: int = 30
    """Pages with fewer words count as short pages outside the main text."""
    long_page_words: int = 1500
    """Pages inside the main text with at least this many words are kept even
    when their title looks like front or back matter."""
    drop_tables: bool = False
    """Leave tables out of the narration."""
    drop_captions: bool = False
    """Leave figure and table captions out of the narration."""


@dataclass(frozen=True, slots=True)
class Decision:
    """What happens to one document of the spine, and why."""

    position: int
    """1-based position in the spine."""
    file_name: str
    title: str
    kind: MatterKind
    reason: str
    narrate: bool
    word_count: int = 0
