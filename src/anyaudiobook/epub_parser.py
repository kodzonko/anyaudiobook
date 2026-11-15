"""Extract chapters from EPUB files."""

import warnings
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from anyaudiobook.models import BookContent

# Silence noisy ebooklib warnings that don't affect parsing.
warnings.filterwarnings(
    "ignore",
    message="In the future version we will turn default option ignore_ncx to True.",
)
warnings.filterwarnings(
    "ignore",
    message="This search incorrectly ignores the root element, and will be fixed in a future version.",
)

FLUFF_TITLES: frozenset[str] = frozenset(
    {
        "Text/dedykacja.xhtml",
        "Podziękowania",
        "Drzewo genealogiczne",
        "Chronologia",
        "",
        "Spis treści:",
    }
)
"""Chapter titles of front/back matter that should not be narrated."""


def is_fluff(title: str) -> bool:
    """Return True if a chapter title marks front/back matter to skip."""
    return title in FLUFF_TITLES


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
        number, separator, title = attribute.partition(". ")
        if separator:
            title = title.replace("„", "").replace("”", "").strip()
            try:
                return int(number), title
            except ValueError:
                return None, title

    return None, heading.get_text().strip()


def parse_document(
    html: str | bytes, fallback_title: str
) -> tuple[int | None, str, str]:
    """Parse one EPUB document into its chapter number, title and plain text.

    Args:
        html: The document's XHTML content.
        fallback_title: Title to use when the document has no heading.

    Returns:
        A ``(chapter_number, title, text)`` triple, see :func:`parse_heading`.
    """
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    number, title = parse_heading(
        heading if isinstance(heading, Tag) else None, fallback_title
    )

    for element in soup(["script", "style"]):
        element.decompose()

    return number, title, soup.get_text().strip()


def read_chapters(epub_path: str | Path) -> list[BookContent]:
    """Split an EPUB file into narratable chapters.

    Documents without text and front/back matter (see :data:`FLUFF_TITLES`)
    are skipped. Chapters without a number in their heading are numbered by
    their position among the kept chapters.

    Args:
        epub_path: Path to the EPUB file.

    Returns:
        The chapters in reading order.
    """
    book = epub.read_epub(str(epub_path))
    chapters: list[BookContent] = []
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        number, title, text = parse_document(item.get_content(), item.get_name())
        if text and not is_fluff(title):
            chapters.append(
                BookContent(
                    chapter_number=number if number is not None else len(chapters) + 1,
                    title=title,
                    content=text,
                )
            )
    return chapters
