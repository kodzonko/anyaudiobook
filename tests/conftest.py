"""Shared pytest fixtures."""

from collections.abc import Callable
from pathlib import Path

import pytest
from ebooklib import epub

from anyaudiobook.models import BookContent

ChapterFactory = Callable[..., BookContent]


@pytest.fixture
def make_chapter() -> ChapterFactory:
    """Return a factory building chapters with sensible defaults."""

    def factory(
        chapter_number: int = 1, title: str = "Title", content: str = "Text"
    ) -> BookContent:
        return BookContent(chapter_number=chapter_number, title=title, content=content)

    return factory


@pytest.fixture
def epub_file(tmp_path: Path) -> Path:
    """Write a small EPUB with numbered chapters, fluff and an empty page."""
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("Test Book")
    book.set_language("en")

    pages = [
        ("intro.xhtml", '<h1 title="1. „Beginning”">Beginning</h1><p>First words.</p>'),
        ("thanks.xhtml", "<h1>Podziękowania</h1><p>Thank you all.</p>"),
        ("blank.xhtml", "<script>var x = 1;</script>"),
        ("end.xhtml", "<h1>The End</h1><p>Last words.</p><style>p {}</style>"),
    ]
    items = []
    for name, body in pages:
        item = epub.EpubHtml(title=name, file_name=name, lang="en")
        item.content = f"<html><body>{body}</body></html>"
        book.add_item(item)
        items.append(item)

    book.toc = items
    book.spine = items
    book.add_item(epub.EpubNcx())

    path = tmp_path / "book.epub"
    epub.write_epub(str(path), book)
    return path


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio tests on asyncio only: edge-tts is built on aiohttp."""
    return "asyncio"
