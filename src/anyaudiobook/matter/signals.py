"""Individual signals that a document is front or back matter.

Each function looks at one kind of evidence and returns a :class:`Verdict`,
or None when that evidence says nothing about the document. They are
combined, and weighed by position in the book, in
:mod:`anyaudiobook.matter.classifier`.
"""

import posixpath
import re
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from itertools import pairwise

from bs4 import Tag

from anyaudiobook.markup import (
    BLOCK_TAGS,
    is_external,
    is_note_markup,
    resolve_href,
    semantic_types,
    text_length,
)
from anyaudiobook.matter.keywords import (
    FILE_NAME_WORDS,
    MAIN_TEXT_TYPES,
    MIN_SUBSTRING_LENGTH,
    SEMANTIC_KINDS,
    TITLE_PHRASES,
    TITLE_PREFIXES,
    fold,
    normalize,
)
from anyaudiobook.matter.models import Document, MatterKind, Verdict

COVERAGE = 0.5
"""Share of a document's text an element must hold to speak for all of it."""

_COPYRIGHT_STRONG = (
    re.compile(r"©|\(c\)\s*\d{4}|\bcopyright\b"),
    re.compile(r"\bisbn\b"),
    re.compile(r"all rights reserved|wszelkie prawa zastrzezone"),
)
_COPYRIGHT_WEAK = (
    re.compile(r"\bredakcja\s*:|\bredaktor prowadzac"),
    re.compile(r"\bkorekta\s*:"),
    re.compile(r"\bsklad\b|\blamanie\b|\btypeset\b"),
    re.compile(r"projekt okladki|cover design"),
    re.compile(r"\bwydanie (?:i|1|pierwsze)\b|first (?:published|edition)"),
    re.compile(r"druk i oprawa|printed in|printed and bound"),
    re.compile(r"tytul oryginalu|original title"),
    re.compile(r"\bprzeklad\b|\btlumaczenie\b|translated by"),
    re.compile(r"library of congress|cataloging.in.publication"),
    re.compile(r"\bwydawnictwo\b|published by"),
    re.compile(r"www\.|https?://"),
)
_COPYRIGHT_MAX_WORDS = 800
_ISBN = re.compile(r"\bisbn\b")
_WORDS_PER_ADVERTISED_ISBN = 150
_PAGE_LIST = r"\d{1,4}(?:\s*[-–—]\s*\d{1,4})?"
_INDEX_LINE = re.compile(rf"^\D.*?,\s*{_PAGE_LIST}(?:\s*,\s*{_PAGE_LIST})*\.?$")
_TOC_LINE = re.compile(r"^\D.{0,150}?(?:\.{2,}|…+|\s)\s*(\d{1,4})$")
_LETTERS = re.compile(r"[a-z]+")


def structural_verdict(document: Document) -> Verdict | None:
    """Judge a document by what the EPUB itself says about it.

    In order: the EPUB 3 navigation document, ``epub:type``/``role`` markup
    on elements holding most of the text (so a chapter with a small notes
    section stays a chapter), and guide or landmark entries pointing at the
    whole document.
    """
    if document.is_nav:
        return Verdict(MatterKind.TOC, "EPUB navigation document")

    total = text_length(document.body)
    types: set[str] = set()
    for element in (document.body, *document.body.find_all(True)):
        if (
            isinstance(element, Tag)
            and (element_types := semantic_types(element))
            and total
            and text_length(element) / total >= COVERAGE
        ):
            types |= element_types
    if verdict := _verdict_for_types(types, "marked {type!r} in its markup"):
        return verdict

    whole = {
        reference.type for reference in document.references if not reference.partial
    }
    return _verdict_for_types(whole, "listed as {type!r} in the book's guide")


def reference_hint(document: Document) -> Verdict | None:
    """Judge a document by guide or landmark entries pointing inside it.

    An entry pointing at a fragment may describe only part of the document,
    so this is a weaker signal than :func:`structural_verdict`.
    """
    partial = {reference.type for reference in document.references if reference.partial}
    verdict = _verdict_for_types(
        partial, "the book's guide lists part of it as {type!r}"
    )
    return verdict if verdict and verdict.kind is not MatterKind.BODY else None


def _verdict_for_types(types: AbstractSet[str], template: str) -> Verdict | None:
    """Turn semantic types into a verdict; main text types win."""
    if main := sorted(types & MAIN_TEXT_TYPES):
        return Verdict(MatterKind.BODY, template.format(type=main[0]))
    if matter := sorted(types & SEMANTIC_KINDS.keys()):
        return Verdict(SEMANTIC_KINDS[matter[0]], template.format(type=matter[0]))
    return None


def content_verdict(document: Document, book_files: AbstractSet[str]) -> Verdict | None:
    """Judge a document by the shape of its content.

    Detects copyright pages, indexes, tables of contents, notes and
    advertisements however they are titled.

    Args:
        document: The document to judge.
        book_files: Names of all documents in the book, to tell links within
            the book from links to the outside.
    """
    folded = fold(document.text)
    lines = document.text.splitlines()
    links = _link_stats(document, book_files)
    total = max(text_length(document.body), 1)

    strong = sum(1 for pattern in _COPYRIGHT_STRONG if pattern.search(folded))
    weak = sum(1 for pattern in _COPYRIGHT_WEAK if pattern.search(folded))
    if strong and strong + weak >= 2 and document.word_count <= _COPYRIGHT_MAX_WORDS:
        return Verdict(
            MatterKind.COPYRIGHT, f"{strong + weak} copyright and imprint markers"
        )

    index_lines = sum(1 for line in lines if _INDEX_LINE.match(line))
    if index_lines >= 8 and index_lines / len(lines) >= 0.5:
        return Verdict(MatterKind.INDEX, f"{index_lines} lines look like index entries")

    if links.internal >= 3 and links.internal_text / total >= 0.6:
        return Verdict(MatterKind.TOC, "mostly links to other parts of the book")
    pages = [int(match[1]) for line in lines if (match := _TOC_LINE.match(line))]
    if len(pages) >= 5 and len(pages) / len(lines) >= 0.6:
        # A table of contents runs through the book; an index jumps around.
        if _rising_share(pages) >= 0.8:
            return Verdict(MatterKind.TOC, f"{len(pages)} lines end in page numbers")
        return Verdict(
            MatterKind.INDEX, f"{len(pages)} lines end in unordered page numbers"
        )

    if (
        links.backlinked_blocks >= 3
        and links.backlinked_blocks / max(links.blocks, 1) >= 0.5
    ):
        return Verdict(MatterKind.NOTES, "most paragraphs link back into the text")
    notes = sum(
        text_length(tag)
        for tag in document.body.find_all(True)
        if isinstance(tag, Tag) and is_note_markup(tag) and not _inside_note(tag)
    )
    if notes / total >= COVERAGE:
        return Verdict(MatterKind.NOTES, "most of the text is marked up as notes")

    # Chapters of technical books cite books by ISBN too, so only a page
    # dense with them is a list of books for sale.
    isbns = len(_ISBN.findall(folded))
    if isbns >= 3 and isbns * _WORDS_PER_ADVERTISED_ISBN >= document.word_count:
        return Verdict(MatterKind.ADVERTISEMENT, f"lists {isbns} ISBNs")
    if links.external >= 3 and document.word_count < 300:
        return Verdict(MatterKind.ADVERTISEMENT, "short page of links to websites")
    return None


def _rising_share(numbers: list[int]) -> float:
    """Return the share of numbers that are at least as big as the previous one."""
    pairs = list(pairwise(numbers))
    return sum(1 for a, b in pairs if b >= a) / len(pairs) if pairs else 1.0


def _inside_note(tag: Tag) -> bool:
    """Return True if an ancestor of ``tag`` is already marked up as a note."""
    return any(is_note_markup(parent) for parent in tag.parents)


@dataclass(slots=True)
class _LinkStats:
    """Counts of the links in a document."""

    internal: int = 0
    """Links to other documents of the book."""
    internal_text: int = 0
    """Characters of link text in links to other documents."""
    external: int = 0
    """Links to websites and other places outside the book."""
    blocks: int = 0
    """Innermost block elements with text."""
    backlinked_blocks: int = 0
    """Of those, the ones linking to a fragment of another document."""


def _link_stats(document: Document, book_files: AbstractSet[str]) -> _LinkStats:
    """Count the links in a document, see :class:`_LinkStats`."""
    stats = _LinkStats()
    for link in document.body.find_all("a", href=True):
        if not isinstance(link, Tag) or not isinstance(href := link.get("href"), str):
            continue
        if is_external(href):
            stats.external += 1
            continue
        target, _ = resolve_href(document.file_name, href)
        if target != document.file_name and target in book_files:
            stats.internal += 1
            stats.internal_text += text_length(link)

    for block in document.body.find_all(BLOCK_TAGS):
        if (
            not isinstance(block, Tag)
            or block.find(BLOCK_TAGS)
            or not text_length(block)
        ):
            continue
        stats.blocks += 1
        for link in block.find_all("a", href=True):
            href = link.get("href") if isinstance(link, Tag) else None
            if isinstance(href, str) and not is_external(href):
                target, fragment = resolve_href(document.file_name, href)
                if fragment and target != document.file_name and target in book_files:
                    stats.backlinked_blocks += 1
                    break
    return stats


def title_verdict(document: Document) -> Verdict | None:
    """Judge a document by its title (headings and table of contents label)."""
    for title in document.titles:
        name = normalize(title)
        if not name:
            continue
        kind = TITLE_PHRASES.get(name)
        if kind is None:
            kind = next(
                (
                    k
                    for prefix, k in TITLE_PREFIXES
                    if name == prefix or name.startswith(prefix + " ")
                ),
                None,
            )
        if kind is not None:
            return Verdict(kind, f"title {title!r} looks like {kind}")
    return None


def filename_verdict(document: Document) -> Verdict | None:
    """Judge a document by the words in its file name."""
    stem = fold(posixpath.splitext(posixpath.basename(document.file_name))[0])
    words = _LETTERS.findall(stem)
    letters = "".join(words)
    for word, kind in FILE_NAME_WORDS.items():
        if word in words or (len(word) >= MIN_SUBSTRING_LENGTH and word in letters):
            return Verdict(kind, f"file name suggests {kind} ({word!r})")
    return None


def short_page_verdict(document: Document, max_words: int) -> Verdict | None:
    """Flag a document with fewer than ``max_words`` words, but some text."""
    if 0 < document.word_count < max_words:
        return Verdict(MatterKind.SHORT_PAGE, f"only {document.word_count} words")
    return None
