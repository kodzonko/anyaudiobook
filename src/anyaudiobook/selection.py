"""Choose which parts of a book to narrate, whatever format it came from."""

import copy
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import Tag

from anyaudiobook.markup import extract_text, remove_unspoken, single_line
from anyaudiobook.matter.classifier import classify_documents
from anyaudiobook.matter.models import Decision, FilterOptions, MatterKind, Verdict
from anyaudiobook.models import BookContent, BookMetadata, Document, SourceBook
from anyaudiobook.readers import read_source


@dataclass(frozen=True, slots=True)
class ParsedBook:
    """A book split into chapters, with the reasoning behind the split."""

    chapters: list[BookContent]
    """The chapters to narrate, in reading order."""
    decisions: list[Decision]
    """One entry per document of the book, narrated or not."""
    metadata: BookMetadata = field(default_factory=BookMetadata)
    """What the book's file says about it."""


def parse_heading(heading: Tag | None, fallback_title: str) -> tuple[int | None, str]:
    """Read the chapter number and title from a chapter's ``<h1>`` tag.

    The number and title come from a ``title="N. Title"`` attribute when it is
    present and well formed; otherwise the heading text, then ``fallback_title``,
    is used as the title and the number is None.

    Args:
        heading: The chapter's first ``<h1>`` tag, if any.
        fallback_title: Title to use when there is no heading.

    Returns:
        A ``(chapter_number, title)`` pair; ``chapter_number`` is None when the
        heading does not carry one.
    """
    if heading is None:
        return None, fallback_title

    attribute = heading.get("title")
    if isinstance(attribute, str):
        number, separator, title = " ".join(attribute.split()).partition(". ")
        if separator:
            title = title.replace("„", "").replace("”", "").strip()
            try:
                return int(number), title
            except ValueError:
                return None, title

    return None, single_line(heading) or fallback_title


def select_chapters(
    book: SourceBook, options: FilterOptions | None = None
) -> ParsedBook:
    """Pick the chapters to narrate from a book, explaining each choice.

    Front and back matter is recognised by
    :func:`anyaudiobook.matter.classifier.classify_documents` and left out as
    ``options`` say; notes, note markers and page numbers are removed from
    the chapters that remain. Chapters without a number in their heading are
    numbered by their position among the narrated chapters.

    Args:
        book: The book, as read by a :class:`anyaudiobook.readers.base.BookReader`.
        options: What to narrate; defaults to :class:`FilterOptions`.

    Returns:
        The chapters, one decision per document and the book's metadata.
    """
    options = options or FilterOptions()
    documents = book.documents
    verdicts = classify_documents(documents, options)
    include = _compile(options.include)
    exclude = _compile(options.exclude)

    chapters: list[BookContent] = []
    decisions: list[Decision] = []
    for position, (document, verdict) in enumerate(
        zip(documents, verdicts, strict=True), start=1
    ):
        heading = document.body.find("h1")
        number, title = parse_heading(
            heading if isinstance(heading, Tag) else None,
            document.toc_label or document.file_name,
        )
        narrate, reason = _choose(
            verdict, (document.file_name, title), options, include, exclude
        )
        decisions.append(
            Decision(
                position=position,
                file_name=document.file_name,
                title=title,
                kind=verdict.kind,
                reason=reason,
                narrate=narrate,
                word_count=document.word_count,
            )
        )
        if narrate:
            chapters.append(
                BookContent(
                    chapter_number=number if number is not None else len(chapters) + 1,
                    title=title,
                    content=narration_text(document, options),
                )
            )
    return ParsedBook(chapters=chapters, decisions=decisions, metadata=book.metadata)


def read_book(path: str | Path, options: FilterOptions | None = None) -> ParsedBook:
    """Read an ebook of any supported format and pick the chapters to narrate.

    Args:
        path: The ebook file.
        options: What to narrate; defaults to :class:`FilterOptions`.

    Returns:
        See :func:`select_chapters`.
    """
    return select_chapters(read_source(path), options)


def narration_text(document: Document, options: FilterOptions) -> str:
    """Return the text to narrate for a document.

    Notes, note markers, page-break markers and navigation are removed (plus
    tables and captions if ``options`` say so). A document consisting only
    of such elements, e.g. a notes page the user chose to narrate, is read in
    full instead.
    """
    body = copy.copy(document.body)
    remove_unspoken(
        body, drop_tables=options.drop_tables, drop_captions=options.drop_captions
    )
    return extract_text(body) or document.text


def _compile(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    """Compile user patterns, ignoring case."""
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def _choose(
    verdict: Verdict,
    names: Sequence[str],
    options: FilterOptions,
    include: Sequence[re.Pattern[str]],
    exclude: Sequence[re.Pattern[str]],
) -> tuple[bool, str]:
    """Decide whether to narrate a document, applying the user's overrides.

    Args:
        verdict: The classifier's verdict.
        names: The document's file name and title, matched against patterns.
        options: The user's settings.
        include: Compiled ``options.include``.
        exclude: Compiled ``options.exclude``.

    Returns:
        Whether to narrate the document, and why.
    """
    if verdict.kind is MatterKind.EMPTY:
        return False, verdict.reason
    for pattern in exclude:
        if any(pattern.search(name) for name in names):
            return False, f"{verdict.reason}; excluded by {pattern.pattern!r}"
    for pattern in include:
        if any(pattern.search(name) for name in names):
            return True, f"{verdict.reason}; included by {pattern.pattern!r}"
    return verdict.kind not in options.skip, verdict.reason
