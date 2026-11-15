"""Tests for EPUB chapter extraction."""

from pathlib import Path
from unittest.mock import Mock, patch

import ebooklib
import pytest
from bs4 import BeautifulSoup, Tag

from anyaudiobook.epub_parser import (
    is_fluff,
    parse_document,
    parse_heading,
    read_chapters,
)


def _heading(html: str) -> Tag:
    """Parse an HTML snippet and return its ``<h1>`` tag."""
    tag = BeautifulSoup(html, "html.parser").find("h1")
    assert isinstance(tag, Tag)
    return tag


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<h1 title="7. Chapter Seven">Heading</h1>', (7, "Chapter Seven")),
        ('<h1 title="3. „Quoted”">Heading</h1>', (3, "Quoted")),
        ('<h1 title="2. Part. Two">Heading</h1>', (2, "Part. Two")),
        ('<h1 title="abc. Named">Heading</h1>', (None, "Named")),
        ('<h1 title="invalid"> Fallback title </h1>', (None, "Fallback title")),
        ("<h1>Untitled heading</h1>", (None, "Untitled heading")),
    ],
)
def test_parse_heading_reads_number_and_title(
    html: str, expected: tuple[int | None, str]
) -> None:
    assert parse_heading(_heading(html), "fallback.xhtml") == expected


def test_parse_heading_without_heading_uses_fallback_title() -> None:
    assert parse_heading(None, "fallback.xhtml") == (None, "fallback.xhtml")


@pytest.mark.parametrize("html", [b"<h1>T</h1><p>Body</p>", "<h1>T</h1><p>Body</p>"])
def test_parse_document_accepts_bytes_and_str(html: str | bytes) -> None:
    assert parse_document(html, "x.xhtml") == (None, "T", "TBody")


def test_parse_document_drops_scripts_and_styles() -> None:
    html = "<p>Keep</p><script>drop()</script><style>p {}</style>"
    assert parse_document(html, "x.xhtml")[2] == "Keep"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Podziękowania", True),
        ("", True),
        ("Spis treści:", True),
        ("Chapter One", False),
    ],
)
def test_is_fluff(title: str, expected: bool) -> None:
    assert is_fluff(title) is expected


def test_read_chapters_numbers_unnumbered_chapters_by_position() -> None:
    items = []
    for content in (
        b'<h1 title="7. Chapter Seven">Heading</h1><p>Text</p>',
        "<h1>Untitled heading</h1><p>Text</p>",
        "<p>No heading</p>",
        '<h1 title="invalid">Fallback title</h1><p>Text</p>',
    ):
        item = Mock()
        item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        item.get_content.return_value = content
        item.get_name.return_value = "fallback.xhtml"
        items.append(item)

    with patch("anyaudiobook.epub_parser.epub.read_epub") as read_epub:
        read_epub.return_value.get_items.return_value = items
        chapters = read_chapters("book.epub")

    assert [(c.chapter_number, c.title) for c in chapters] == [
        (7, "Chapter Seven"),
        (2, "Untitled heading"),
        (3, "fallback.xhtml"),
        (4, "Fallback title"),
    ]


def test_read_chapters_from_real_epub_skips_fluff_and_empty_pages(
    epub_file: Path,
) -> None:
    chapters = read_chapters(epub_file)

    assert [(c.chapter_number, c.title) for c in chapters] == [
        (1, "Beginning"),
        (2, "The End"),
    ]
    assert "First words." in chapters[0].content
    assert "p {}" not in chapters[1].content
