"""XHTML helpers: semantic markup, unspoken elements and narratable text."""

import posixpath
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "caption",
        "dd",
        "details",
        "dialog",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
"""Elements whose content is narrated as a line of its own."""

NOTE_TYPES: frozenset[str] = frozenset(
    {
        "annoref",
        "annotation",
        "backlink",
        "endnote",
        "endnotes",
        "footnote",
        "footnotes",
        "note",
        "noteref",
        "rearnote",
        "rearnotes",
        "doc-backlink",
        "doc-endnote",
        "doc-endnotes",
        "doc-footnote",
        "doc-noteref",
    }
)
"""``epub:type`` and ``role`` tokens of notes and note references."""

UNSPOKEN_TYPES: frozenset[str] = NOTE_TYPES | {
    "doc-pagebreak",
    "doc-pagelist",
    "doc-toc",
    "landmarks",
    "page-list",
    "pagebreak",
    "toc",
}
"""``epub:type`` and ``role`` tokens of elements that are never narrated."""

_LINE_BREAK_TAGS = frozenset({"br", "hr"})
_BREAK = " "
_HEADINGS = ("h1", "h2", "h3")

_NOTE_CLASS = re.compile(r"footnote|endnote|przypis|noteref|fnref", re.IGNORECASE)
_SUP_MARKER = re.compile(r"[\[(]?\s*(?:\d{1,4}|[a-z]|[*†‡§]+)\s*[\])]?", re.IGNORECASE)
_LINK_MARKER = re.compile(r"\[\s*(?:\d{1,4}|[a-z]|[*†‡§]+)\s*\]|[*†‡§]+", re.IGNORECASE)
_NOTE_ID = re.compile(r"fn|note|nota|przyp|ftn|ref", re.IGNORECASE)
_EXTERNAL_SCHEMES = frozenset({"http", "https", "mailto", "ftp", "tel"})


def semantic_types(tag: Tag) -> frozenset[str]:
    """Return the lowercased ``epub:type`` and ``role`` tokens of ``tag``."""
    tokens: set[str] = set()
    for attribute in ("epub:type", "role"):
        value = tag.get(attribute)
        if isinstance(value, list):
            value = " ".join(value)
        if isinstance(value, str):
            tokens.update(value.lower().split())
    return frozenset(tokens)


def class_names(tag: Tag) -> list[str]:
    """Return the CSS class names of ``tag``."""
    value = tag.get("class")
    if isinstance(value, str):
        return value.split()
    return list(value) if isinstance(value, list) else []


def is_note_markup(tag: Tag) -> bool:
    """Return True if ``tag`` is marked up as a note or a note reference.

    Both semantic markup (``epub:type``/``role``) and the class names that
    common ebook tools use for footnotes (``footnote``, ``przypis``, ...)
    count.
    """
    return bool(semantic_types(tag) & NOTE_TYPES) or any(
        _NOTE_CLASS.search(name) for name in class_names(tag)
    )


def text_length(tag: Tag) -> int:
    """Return the number of non-whitespace characters in ``tag``'s text."""
    return sum(len(chunk) for chunk in tag.get_text().split())


def body_of(soup: BeautifulSoup) -> Tag:
    """Return the document's ``<body>``, or the whole soup when it has none.

    Narrating only the body keeps ``<head>`` content such as ``<title>``
    (which ebook tools often fill with the book title) out of the audio.
    """
    body = soup.find("body")
    return body if isinstance(body, Tag) else soup


def parse_html(html: str | bytes) -> Tag:
    """Parse an XHTML document and return its body without scripts and styles."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return body_of(soup)


def heading_titles(root: Tag) -> list[str]:
    """Return title candidates from the first heading of ``root``.

    These are the text of the first ``<h1>``–``<h3>`` and the ``title``
    attribute of the first ``<h1>``, when present.
    """
    titles: list[str] = []
    heading = root.find(_HEADINGS)
    if isinstance(heading, Tag):
        titles.append(single_line(heading))
    h1 = root.find("h1")
    if isinstance(h1, Tag):
        attribute = h1.get("title")
        if isinstance(attribute, str):
            titles.append(" ".join(attribute.split()))
    return [title for title in titles if title]


def single_line(root: Tag) -> str:
    """Return the text of ``root`` on one line, e.g. for a multi-line heading.

    ``<h1>Rozdział 1.<br/>Początek</h1>`` becomes ``"Rozdział 1. Początek"``.
    """
    return " ".join(extract_text(root).split())


def resolve_href(base: str, href: str) -> tuple[str, str]:
    """Resolve a link found in document ``base`` to a book file and fragment.

    Args:
        base: Name of the document holding the link, e.g. ``Text/ch1.xhtml``.
        href: The link target, relative to ``base``.

    Returns:
        A ``(file_name, fragment)`` pair; links to a fragment of the same
        document resolve to ``base`` itself.
    """
    path, _, fragment = unquote(href.strip()).partition("#")
    if not path:
        return base, fragment
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), path)), fragment


def is_external(href: str) -> bool:
    """Return True if ``href`` points outside the book, e.g. to a website."""
    href = href.strip()
    return urlsplit(href).scheme.lower() in _EXTERNAL_SCHEMES or href.startswith("www.")


def remove_unspoken(
    root: Tag, *, drop_tables: bool = False, drop_captions: bool = False
) -> None:
    """Remove elements that should not be read aloud, in place.

    Removed are footnotes and endnotes, note reference markers (``¹``,
    ``[1]``, ``*``), page-break markers and navigation blocks. Superscript
    numbers that directly follow a digit (``10<sup>6</sup>``) and are not
    links are kept, as they are more likely exponents than note markers.

    Args:
        root: The element to clean, usually a document body.
        drop_tables: Also remove tables.
        drop_captions: Also remove figure and table captions.
    """
    doomed: list[Tag] = []
    for tag in root.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if (
            tag.name == "nav"
            or semantic_types(tag) & UNSPOKEN_TYPES
            or is_note_markup(tag)
            or (tag.name == "sup" and _is_marker_sup(tag))
            or (tag.name == "a" and _is_marker_link(tag))
            or (drop_tables and tag.name == "table")
            or (drop_captions and tag.name in ("figcaption", "caption"))
        ):
            doomed.append(tag)
    for tag in doomed:
        if not tag.decomposed:
            tag.decompose()


def _is_marker_sup(sup: Tag) -> bool:
    """Return True if a ``<sup>`` element holds a note marker."""
    if not _SUP_MARKER.fullmatch(sup.get_text().strip()):
        return False
    if sup.find_parent("a", href=True) or sup.find("a", href=True):
        return True
    previous = sup.find_previous(string=True)
    return not (previous is not None and str(previous)[-1:].isdigit())


def _is_marker_link(link: Tag) -> bool:
    """Return True if an ``<a>`` element is a note reference marker."""
    href = link.get("href")
    if not isinstance(href, str) or "#" not in href:
        return False
    text = link.get_text().strip()
    if _LINK_MARKER.fullmatch(text):
        return True
    identifier = link.get("id")
    hint = (
        href.partition("#")[2]
        + " "
        + (identifier if isinstance(identifier, str) else "")
    )
    return text.isdigit() and len(text) <= 4 and bool(_NOTE_ID.search(hint))


def extract_text(root: Tag) -> str:
    """Return the text of ``root`` with one line per block element.

    Whitespace inside a block collapses into single spaces, so inline markup
    and source line wrapping never split a sentence, while block boundaries
    (paragraphs, headings, list items, ``<br>``) become line breaks that give
    the narrator a pause. Comments and other non-text nodes are ignored.
    """
    parts: list[str] = []
    _collect_text(root, parts)
    lines = (" ".join(chunk.split()) for chunk in "".join(parts).split(_BREAK))
    return "\n".join(line for line in lines if line)


def _collect_text(node: Tag, parts: list[str]) -> None:
    """Append the text under ``node`` to ``parts``, marking block boundaries."""
    for child in node.children:
        if isinstance(child, Tag):
            if child.name in _LINE_BREAK_TAGS:
                parts.append(_BREAK)
                continue
            block = child.name in BLOCK_TAGS
            if block:
                parts.append(_BREAK)
            _collect_text(child, parts)
            if block:
                parts.append(_BREAK)
        elif type(child) is NavigableString:
            parts.append(child)
