"""Split one long HTML document into the parts of a book.

DOCX, TXT, HTML, PDF and old Kindle books all arrive as a single HTML body.
This module cuts it into sections the way an EPUB is cut into spine
documents, so the classifier can judge each part separately. Where a
section starts is decided, in order of preference, by:

1. **Table of contents entries** — elements carrying :data:`TOC_LABEL`,
   set by readers that know the book's real TOC (PDF outlines, Kindle
   NCX). Their label becomes the section's TOC label.
2. **Headings** — every ``<h1>`` up to the deepest level used for
   chapters, see :func:`heading_split_level`. Paragraphs that only look
   like headings are promoted first (:mod:`anyaudiobook.readers.headings`).
3. **Page breaks** — ``<mbp:pagebreak>`` in old Kindle books.

Collections of notes (``epub:type="endnotes"`` and the like) always start a
section of their own, so they can be skipped without losing the chapter
before them.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

from anyaudiobook.markup import semantic_types, single_line, text_length
from anyaudiobook.readers.headings import has_headings, promote_headings

TOC_LABEL = "data-toc-label"
"""Attribute marking where a table of contents entry starts; its value is
the entry's label."""

NOTE_COLLECTION_TYPES: frozenset[str] = frozenset(
    {"endnotes", "footnotes", "rearnotes", "doc-endnotes"}
)
"""``epub:type``/``role`` tokens of a collection of notes."""

_PAGE_BREAKS = frozenset({"mbp:pagebreak"})
_HEADING_LEVELS = (1, 2, 3)
_MEDIA = ("img", "svg", "image")

BreakRule = Callable[[Tag], bool]


@dataclass(slots=True)
class Section:
    """One part cut out of a long document."""

    label: str | None
    """Its label in the table of contents (or its heading), if any."""
    body: Tag
    """A ``<body>`` holding the part's content."""


def split_sections(
    body: Tag, class_sizes: Mapping[str, float] | None = None
) -> list[Section]:
    """Cut ``body`` into sections, moving its content into new bodies.

    Args:
        body: The whole book as one HTML body; emptied by the split.
        class_sizes: Font sizes by CSS class, used to find headings in
            documents without heading markup.

    Returns:
        The sections in reading order. Parts without any text or image are
        left out.
    """
    has_toc = body.find(True, attrs={TOC_LABEL: True}) is not None
    if not has_toc and not has_headings(body):
        promote_headings(body, class_sizes)
    is_break = _break_rule(body, has_toc)

    groups: list[tuple[str | None, list[PageElement]]] = [(None, [])]
    for node in _flatten(body, is_break):
        lead = _leading_break(node, is_break) if isinstance(node, Tag) else None
        if lead is not None:
            groups.append((_label(lead), []))
        groups[-1][1].append(node)
    return [
        Section(label, _new_body(nodes))
        for label, nodes in groups
        if _has_content(nodes)
    ]


def mark_toc(body: Tag, toc: Mapping[str, str]) -> None:
    """Mark the elements a separate table of contents points at, in place.

    Args:
        body: The document body.
        toc: Element id → TOC entry label, e.g. from a Kindle NCX file.
            Ids missing from the body are ignored.
    """
    for identifier, label in toc.items():
        element = body.find(id=identifier)
        if isinstance(element, Tag) and not element.has_attr(TOC_LABEL):
            element[TOC_LABEL] = label


def heading_split_level(body: Tag) -> int | None:
    """Return the deepest heading level that starts a part of the book.

    That is the shallowest level used at least twice (a book whose only
    ``<h1>`` is its title is split at ``<h2>``), else the shallowest level
    used at all, else None.
    """
    counts = {
        level: sum(
            1
            for heading in body.find_all(f"h{level}")
            if isinstance(heading, Tag) and text_length(heading)
        )
        for level in _HEADING_LEVELS
    }
    for minimum in (2, 1):
        for level in _HEADING_LEVELS:
            if counts[level] >= minimum:
                return level
    return None


def toc_depth(levels: Sequence[int], minimum: int = 3, deepest: int = 3) -> int:
    """Choose how deep into a nested table of contents to split the book.

    Returns the shallowest depth whose entries (with the ones above them)
    number at least ``minimum``: a book's outline often has one top-level
    entry, the title, with the chapters below it.

    Args:
        levels: The level (1 = top) of every TOC entry.
        minimum: Fewest entries worth splitting at.
        deepest: Deepest level ever used.
    """
    for depth in range(1, deepest + 1):
        if sum(1 for level in levels if level <= depth) >= minimum:
            return depth
    return deepest


def relink(sections: Sequence[tuple[str, Tag]]) -> None:
    """Point links at the section holding their target, in place.

    After a split, ``href="#note-3"`` may refer to an element that now
    lives in another section. Rewriting it to ``section-009#note-3`` keeps
    the link signals of the classifier working (a table of contents is
    mostly links to other parts, notes link back into the chapters).

    Args:
        sections: ``(name, body)`` pairs, the names the documents will have.
    """
    owners: dict[str, str] = {}
    for name, body in sections:
        for element in body.find_all(id=True):
            identifier = element.get("id") if isinstance(element, Tag) else None
            if isinstance(identifier, str):
                owners.setdefault(identifier, name)
    for name, body in sections:
        for link in body.find_all("a", href=True):
            href = link.get("href") if isinstance(link, Tag) else None
            if not isinstance(href, str) or not href.startswith("#"):
                continue
            target = owners.get(unquote(href[1:]))
            if target is not None and target != name:
                link["href"] = f"{target}{href}"


def _break_rule(body: Tag, has_toc: bool) -> BreakRule:
    """Return the test telling which elements start a new section."""
    if has_toc:
        return lambda tag: tag.has_attr(TOC_LABEL) or _is_note_collection(tag)
    level = heading_split_level(body)
    if level is not None:
        names = frozenset(f"h{n}" for n in range(1, level + 1))
        return lambda tag: (
            (tag.name in names and bool(text_length(tag))) or _is_note_collection(tag)
        )
    return lambda tag: tag.name in _PAGE_BREAKS or _is_note_collection(tag)


def _is_note_collection(tag: Tag) -> bool:
    """Return True if ``tag`` is marked up as a collection of notes."""
    return bool(semantic_types(tag) & NOTE_COLLECTION_TYPES)


def _label(tag: Tag) -> str | None:
    """Return the TOC label of the element starting a section."""
    label = tag.get(TOC_LABEL)
    if isinstance(label, str):
        return " ".join(label.split()) or None
    if tag.name and tag.name[:1] == "h" and tag.name[1:].isdigit():
        return single_line(tag) or None
    return None


def _flatten(container: Tag, is_break: BreakRule) -> Iterator[PageElement]:
    """Yield the children of ``container``, opening up wrappers.

    A wrapper (``<div>``, ``<section>``, ...) holding a section start other
    than at its very beginning is replaced by its children, recursively, so
    every section start ends up at the top level. Wrappers that only begin
    with one, and the section starts themselves, are kept whole.
    """
    for child in list(container.children):
        if (
            isinstance(child, Tag)
            and not is_break(child)
            and _has_inner_break(child, is_break)
        ):
            yield from _flatten(child, is_break)
        else:
            yield child


def _has_inner_break(tag: Tag, is_break: BreakRule) -> bool:
    """Return True if ``tag`` holds a section start past its beginning."""
    lead = _leading_break(tag, is_break)
    return any(
        isinstance(element, Tag) and element is not lead and is_break(element)
        for element in tag.find_all(True)
    )


def _leading_break(tag: Tag, is_break: BreakRule) -> Tag | None:
    """Return the section start that ``tag`` begins with, if any."""
    node = tag
    while True:
        if is_break(node):
            return node
        first = next((child for child in node.children if not _is_blank(child)), None)
        if not isinstance(first, Tag):
            return None
        node = first


def _is_blank(node: PageElement) -> bool:
    """Return True for whitespace and non-text nodes such as comments."""
    if isinstance(node, Tag):
        return False
    return type(node) is not NavigableString or not node.strip()


def _has_content(nodes: Sequence[PageElement]) -> bool:
    """Return True if the nodes hold any text or image."""
    for node in nodes:
        if isinstance(node, Tag):
            if text_length(node) or node.name in _MEDIA or node.find(_MEDIA):
                return True
        elif type(node) is NavigableString and node.strip():
            return True
    return False


def _new_body(nodes: Sequence[PageElement]) -> Tag:
    """Move ``nodes`` into a new ``<body>`` element and return it."""
    soup = BeautifulSoup("", "html.parser")
    body = soup.new_tag("body")
    soup.append(body)
    for node in nodes:
        body.append(node.extract())
    return body
