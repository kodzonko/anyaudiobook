"""Shared pytest fixtures."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from ebooklib import epub

from anyaudiobook.models import BookContent

ChapterFactory = Callable[..., BookContent]


@dataclass(frozen=True)
class Page:
    """One XHTML page of a test EPUB."""

    name: str
    body: str
    toc: str | None = None
    """Label in the table of contents; the page is left out of it when None."""
    linear: bool = True
    head_title: str = ""


EpubFactory = Callable[..., Path]


@pytest.fixture
def make_epub(tmp_path: Path) -> EpubFactory:
    """Return a factory writing EPUB files from :class:`Page` lists.

    The factory takes the pages in manifest order and optionally
    ``spine`` (page names in reading order, ``"nav"`` for the navigation
    document) and ``guide`` (EPUB 2 guide entries, also written as EPUB 3
    landmarks by ebooklib).
    """

    def factory(
        pages: Sequence[Page],
        *,
        spine: Sequence[str] | None = None,
        guide: Sequence[dict[str, str]] = (),
        name: str = "book.epub",
    ) -> Path:
        book = epub.EpubBook()
        book.set_identifier("test-book")
        book.set_title("Test Book")
        book.set_language("en")

        items: dict[str, epub.EpubHtml] = {}
        for page in pages:
            item = epub.EpubHtml(title=page.head_title, file_name=page.name, lang="en")
            item.content = f"<html><body>{page.body}</body></html>"
            book.add_item(item)
            items[page.name] = item

        book.toc = [
            epub.Link(page.name, page.toc, f"toc-{index}")
            for index, page in enumerate(pages)
            if page.toc
        ]
        linear = {page.name: page.linear for page in pages}
        order = spine if spine is not None else [page.name for page in pages]
        book.spine = [
            "nav"
            if entry == "nav"
            else (items[entry], "yes" if linear[entry] else "no")
            for entry in order
        ]
        book.guide = list(guide)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        path = tmp_path / name
        epub.write_epub(str(path), book)
        return path

    return factory


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
