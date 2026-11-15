"""Read PDF files that have a text layer (not scans) with PyMuPDF.

A PDF has no paragraphs or headings, only lines placed on pages, so the
reader rebuilds them from the layout:

* **Headings** are lines in a font clearly bigger than the body text.
* **Paragraphs** are lines joined until a vertical gap, an indented line or
  a short line ending a sentence; hyphenated words are rejoined, also
  across pages.
* **Running headers, footers and page numbers** are lines in the top or
  bottom margin that are page numbers or repeat on several pages; they are
  dropped.
* **Footnotes** are lines in a small font below the text of a page, starting
  with a marker; superscript note markers become ``<sup>``. Both are then
  removed by the shared clean-up of :func:`anyaudiobook.markup.remove_unspoken`.
* **Chapters** come from the PDF's outline (bookmarks) when it has one,
  otherwise from the headings, see :mod:`anyaudiobook.readers.splitting`.
"""

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import pymupdf
from bs4 import Tag

from anyaudiobook.errors import UnreadableBookError
from anyaudiobook.models import BookMetadata, CoverImage
from anyaudiobook.readers.base import HtmlBookReader, HtmlSource
from anyaudiobook.readers.headings import H1_RATIO, H2_RATIO, MAX_HEADING_LENGTH
from anyaudiobook.readers.lines import join_lines
from anyaudiobook.readers.splitting import TOC_LABEL, toc_depth

MIN_CHARS_PER_PAGE = 20
"""A PDF with less text than this per page is taken for a scan."""

MARGIN = 0.1
"""Share of the page height, at the top and at the bottom, where running
headers, footers and page numbers are looked for."""

FOOTNOTE_RATIO = 0.85
"""Lines this much smaller than the body text, below it, may be footnotes."""

PAGE = "data-page"
"""Attribute holding the page (1-based) a paragraph starts on."""
PAGE_END = "data-page-end"
"""Attribute holding the page a paragraph ends on, when it spans pages."""

_FLAGS = pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES
_SUPERSCRIPT_RATIO = 0.8
_COVER_ZOOM = 1.5
_SENTENCE_END = re.compile(r"[.!?…:;\"”»)\]]$")
_FOOTNOTE_START = re.compile(r"^\s*(?:\d{1,3}|[*†‡§]+|\[\d{1,3}\]|\(\d{1,3}\))[\s.)]")
_PAGE_NUMBER = re.compile(
    r"^[\W_]*(?:page\s+|str\.\s*|s\.\s*)?(?:\d{1,4}|[ivxlcdm]{1,7})"
    r"(?:\s*(?:/|of|z)\s*\d{1,4})?[\W_]*$",
    re.IGNORECASE,
)
_DIGITS = re.compile(r"\d+")
_NOT_A_TITLE = re.compile(
    r"^microsoft word\b|\.(?:docx?|pdf|indd|tex|odt)$", re.IGNORECASE
)


@dataclass(slots=True)
class _Line:
    """One line of text on a page, in PyMuPDF coordinates (y grows down)."""

    page: int
    """1-based page number."""
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    """The font size of most of the line's characters."""
    text: str
    html: str
    """The text, escaped, with superscripts in ``<sup>``."""
    page_height: float


class PdfReader(HtmlBookReader):
    """Reads PDF files with a text layer; scanned PDFs need OCR first."""

    suffixes = (".pdf",)

    def __init__(self, *, outline_depth: int | None = None, cover: bool = True) -> None:
        """Configure the reader.

        Args:
            outline_depth: Deepest outline level that starts a chapter. By
                default the shallowest level with at least three entries,
                so a lone top-level entry holding the whole book is skipped.
            cover: Use the first page as cover art when it holds an image.
        """
        self.outline_depth = outline_depth
        self.cover = cover

    def load(self, path: Path) -> HtmlSource:
        """Rebuild the PDF's text as one HTML document.

        Raises:
            UnreadableBookError: If the file is not a PDF, is password
                protected or has (almost) no text layer.
        """
        try:
            document = pymupdf.open(path)
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError) as error:
            raise UnreadableBookError(f"Cannot read PDF {path}: {error}") from error
        with document:
            if document.needs_pass:
                raise UnreadableBookError(f"{path} is password protected")
            lines = list(_read_lines(document))
            if sum(len(line.text) for line in lines) < MIN_CHARS_PER_PAGE * max(
                document.page_count, 1
            ):
                raise UnreadableBookError(
                    f"{path} has (almost) no text layer, it is probably scanned; "
                    "make it searchable with OCR first (e.g. ocrmypdf)"
                )
            body_size = _body_size(lines)
            lines = _drop_running_heads(lines, body_size)
            marks = _outline_marks(
                document.get_toc(simple=False), lines, self.outline_depth
            )
            html = _render(lines, body_size, marks)
            metadata = _metadata(document, cover=self.cover)
        return HtmlSource(html, metadata)

    def section_name(self, index: int, body: Tag) -> str:
        """Name a section after its pages, e.g. ``pages 12-18``."""
        pages = [
            int(value)
            for tag in body.find_all(True, attrs={PAGE: True})
            if isinstance(tag, Tag)
            for value in (tag.get(PAGE), tag.get(PAGE_END))
            if isinstance(value, str) and value.isdigit()
        ]
        if not pages:
            return super().section_name(index, body)
        first, last = min(pages), max(pages)
        return f"page {first}" if first == last else f"pages {first}-{last}"


def _read_lines(document: Any) -> Iterator[_Line]:
    """Yield every horizontal line of text in the document, in reading order."""
    for page in document:
        height = page.rect.height
        data = page.get_text("dict", flags=_FLAGS, sort=True)
        for block in data["blocks"]:
            for line in block.get("lines", ()):
                if line.get("dir", (1, 0))[1] != 0:
                    continue  # rotated text, e.g. along the margin
                if parsed := _parse_line(line, page.number + 1, height):
                    yield parsed


def _parse_line(line: Mapping[str, Any], page: int, height: float) -> _Line | None:
    """Turn a PyMuPDF line into a :class:`_Line`, marking superscripts."""
    spans = [span for span in line["spans"] if span["text"].strip()]
    if not spans:
        return None
    weights: Counter[float] = Counter()
    for span in spans:
        weights[round(span["size"], 1)] += len(span["text"].strip())
    size = weights.most_common(1)[0][0]
    baseline = max(
        (span["origin"][1] for span in spans if round(span["size"], 1) == size),
        default=spans[0]["origin"][1],
    )
    parts: list[str] = []
    for span in line["spans"]:
        text = escape(span["text"])
        raised = span["origin"][1] < baseline - 0.2 * size
        small = span["size"] < size * _SUPERSCRIPT_RATIO
        superscript = span["flags"] & pymupdf.TEXT_FONT_SUPERSCRIPT or (
            raised and small
        )
        if superscript and text.strip():
            text = f"<sup>{text.strip()}</sup>"
        parts.append(text)
    x0, y0, x1, y1 = line["bbox"]
    return _Line(
        page=page,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        size=size,
        text=" ".join("".join(span["text"] for span in line["spans"]).split()),
        html="".join(parts).strip(),
        page_height=height,
    )


def _body_size(lines: Sequence[_Line]) -> float:
    """Return the font size of most of the text, weighted by characters."""
    weights: Counter[float] = Counter()
    for line in lines:
        weights[round(line.size * 2) / 2] += len(line.text)
    return weights.most_common(1)[0][0]


def _in_margin(line: _Line) -> bool:
    """Return True if the line sits in the top or bottom margin."""
    return line.y1 <= line.page_height * MARGIN or line.y0 >= line.page_height * (
        1 - MARGIN
    )


def _drop_running_heads(lines: list[_Line], body_size: float) -> list[_Line]:
    """Remove page numbers and running headers and footers.

    A margin line in body-size or smaller type is dropped when it is a page
    number or when its text, digits aside, appears on at least two pages.
    Bigger margin lines are headings and stay.
    """
    candidates = [
        line for line in lines if _in_margin(line) and line.size <= body_size * 1.05
    ]
    pages: defaultdict[str, set[int]] = defaultdict(set)
    for line in candidates:
        pages[_head_key(line.text)].add(line.page)
    doomed = {
        id(line)
        for line in candidates
        if _PAGE_NUMBER.match(line.text) or len(pages[_head_key(line.text)]) >= 2
    }
    return [line for line in lines if id(line) not in doomed]


def _head_key(text: str) -> str:
    """Reduce a running header to what stays the same from page to page."""
    return " ".join(_DIGITS.sub("#", text.casefold()).split())


def _outline_marks(
    toc: Sequence[Sequence[Any]], lines: Sequence[_Line], depth: int | None
) -> dict[int, str]:
    """Map line positions to the outline entry starting there.

    Args:
        toc: ``Document.get_toc(simple=False)``: ``[level, title, page,
            destination]`` entries.
        lines: The lines that will be rendered.
        depth: Deepest outline level to use; see :class:`PdfReader`.

    Returns:
        ``{line index: entry title}`` for the chosen entries.
    """
    entries = [entry for entry in toc if entry[2] >= 1 and str(entry[1]).strip()]
    if not entries or not lines:
        return {}
    depth = depth or toc_depth([entry[0] for entry in entries])
    marks: dict[int, str] = {}
    for level, title, page, *rest in entries:
        if level > depth:
            continue
        destination = rest[0] if rest and isinstance(rest[0], dict) else {}
        point = destination.get("to")
        top = getattr(point, "y", math.nan)
        index = next(
            (
                position
                for position, line in enumerate(lines)
                if line.page > page
                or (
                    line.page == page
                    and (math.isnan(top) or line.y0 >= top - line.size)
                )
            ),
            None,
        )
        if index is not None and index not in marks:
            marks[index] = " ".join(str(title).split())
    return marks


@dataclass(slots=True)
class _Paragraph:
    """Lines rendered as one HTML element."""

    tag: str
    lines: list[_Line]
    label: str | None = None


def _render(lines: Sequence[_Line], body_size: float, marks: Mapping[int, str]) -> str:
    """Rebuild paragraphs, headings and footnotes as an HTML document."""
    footnotes = _footnote_lines(lines, body_size)
    right_edges: defaultdict[int, float] = defaultdict(float)
    for line in lines:
        right_edges[line.page] = max(right_edges[line.page], line.x1)

    paragraphs: list[_Paragraph] = []
    for index, line in enumerate(lines):
        tag = "aside" if id(line) in footnotes else _block_tag(line, body_size)
        current = paragraphs[-1] if paragraphs else None
        if (
            current is None
            or index in marks
            or current.tag != tag
            or _starts_paragraph(current, line, right_edges[current.lines[-1].page])
        ):
            paragraphs.append(_Paragraph(tag, [line], marks.get(index)))
        else:
            current.lines.append(line)
    return "<html><body>" + "".join(map(_paragraph_html, paragraphs)) + "</body></html>"


def _block_tag(line: _Line, body_size: float) -> str:
    """Return the element a line belongs to: ``h1``, ``h2`` or ``p``."""
    if len(line.text) <= MAX_HEADING_LENGTH:
        if line.size >= body_size * H1_RATIO:
            return "h1"
        if line.size >= body_size * H2_RATIO:
            return "h2"
    return "p"


def _footnote_lines(lines: Sequence[_Line], body_size: float) -> set[int]:
    """Return the ids of lines that are footnotes at the bottom of a page."""
    by_page: defaultdict[int, list[_Line]] = defaultdict(list)
    for line in lines:
        by_page[line.page].append(line)
    found: set[int] = set()
    for page_lines in by_page.values():
        body_bottom = max(
            (line.y1 for line in page_lines if line.size > body_size * FOOTNOTE_RATIO),
            default=None,
        )
        if body_bottom is None:
            continue
        started = False
        for line in page_lines:
            below = line.y0 >= body_bottom - 1 and line.y0 > line.page_height / 2
            if not below or line.size > body_size * FOOTNOTE_RATIO:
                continue
            started = started or bool(_FOOTNOTE_START.match(line.text))
            if started:
                found.add(id(line))
    return found


def _starts_paragraph(current: _Paragraph, line: _Line, right_edge: float) -> bool:
    """Return True if ``line`` does not continue the paragraph ``current``."""
    previous = current.lines[-1]
    ends_sentence = bool(_SENTENCE_END.search(previous.text))
    if current.tag in ("h1", "h2"):
        return (
            line.page != previous.page
            or len(current.lines) >= 3
            or line.y0 - previous.y1 > line.size
        )
    if line.page != previous.page:
        return ends_sentence
    pitch = line.y0 - previous.y0
    return (
        pitch < 0  # moved up: a new column
        or pitch > 1.7 * line.size  # extra space between paragraphs
        or line.x0 > previous.x0 + 0.8 * line.size  # indented first line
        or (ends_sentence and previous.x1 < right_edge - 3 * line.size)
    )


def _paragraph_html(paragraph: _Paragraph) -> str:
    """Render a paragraph as an HTML element."""
    first, last = paragraph.lines[0].page, paragraph.lines[-1].page
    attributes = f' {PAGE}="{first}"'
    if last != first:
        attributes += f' {PAGE_END}="{last}"'
    if paragraph.label:
        attributes += f' {TOC_LABEL}="{escape(paragraph.label)}"'
    if paragraph.tag == "aside":
        attributes += ' epub:type="footnote"'
    text = join_lines(line.html for line in paragraph.lines)
    return f"<{paragraph.tag}{attributes}>{text}</{paragraph.tag}>"


def _metadata(document: Any, *, cover: bool) -> BookMetadata:
    """Return the title and authors from the PDF's info, and its cover."""
    info = document.metadata or {}
    title = (info.get("title") or "").strip()
    authors = tuple(
        name.strip() for name in (info.get("author") or "").split(";") if name.strip()
    )
    image = None
    if cover and document.page_count and document[0].get_images():
        pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(_COVER_ZOOM, _COVER_ZOOM))
        image = CoverImage(pixmap.tobytes("jpeg", jpg_quality=85), "image/jpeg")
    return BookMetadata(
        title=title if title and not _NOT_A_TITLE.search(title) else None,
        authors=authors,
        cover=image,
    )
