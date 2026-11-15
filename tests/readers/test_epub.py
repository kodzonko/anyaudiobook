"""Tests for EPUB reading and chapter selection, on real EPUB files."""

import zipfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from anyaudiobook import UnreadableBookError
from anyaudiobook.matter import (
    DEFAULT_SKIP,
    FilterOptions,
    MatterKind,
    classify_documents,
)
from anyaudiobook.models import Reference
from anyaudiobook.readers.epub import load_documents
from anyaudiobook.selection import parse_heading, read_book, read_chapters
from tests.conftest import EpubFactory, Page

LONG = " ".join(["word"] * 200)
"""Enough words for a page to count as a chapter rather than a short page."""


def _heading(html: str) -> Tag:
    """Parse an HTML snippet and return its ``<h1>`` tag."""
    tag = BeautifulSoup(html, "html.parser").find("h1")
    assert isinstance(tag, Tag)
    return tag


def _chapter(
    name: str, title: str, *, toc: str | None = None, linear: bool = True
) -> Page:
    """Return a page holding a long chapter with an ``<h1>`` title."""
    return Page(name, f"<h1>{title}</h1><p>{LONG}</p>", toc=toc, linear=linear)


def _html(body: str, body_attributes: str = "") -> str:
    """Wrap body HTML in a full document."""
    return f"<html><head><title>Book</title></head><body {body_attributes}>{body}</body></html>"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<h1 title="7. Chapter Seven">Heading</h1>', (7, "Chapter Seven")),
        ('<h1 title="3. „Quoted”">Heading</h1>', (3, "Quoted")),
        ('<h1 title="2. Part. Two">Heading</h1>', (2, "Part. Two")),
        ('<h1 title="abc. Named">Heading</h1>', (None, "Named")),
        ('<h1 title="invalid"> Fallback title </h1>', (None, "Fallback title")),
        ("<h1>Untitled heading</h1>", (None, "Untitled heading")),
        ("<h1> </h1>", (None, "fallback.xhtml")),
        ("<h1>Rozdział 1.<br/>Początek</h1>", (None, "Rozdział 1. Początek")),
        ('<h1 title="4. Multi\n  line">x</h1>', (4, "Multi line")),
    ],
)
def test_parse_heading_reads_number_and_title(
    html: str, expected: tuple[int | None, str]
) -> None:
    assert parse_heading(_heading(html), "fallback.xhtml") == expected


def test_parse_heading_without_heading_uses_fallback_title() -> None:
    assert parse_heading(None, "fallback.xhtml") == (None, "fallback.xhtml")


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


def test_read_book_numbers_unnumbered_chapters_by_position(
    make_epub: EpubFactory,
) -> None:
    path = make_epub(
        [
            Page("a.xhtml", f'<h1 title="7. Chapter Seven">Heading</h1><p>{LONG}</p>'),
            _chapter("b.xhtml", "Untitled heading"),
            Page("c.xhtml", f"<p>{LONG}</p>"),
            Page("d.xhtml", f'<h1 title="invalid">Fallback title</h1><p>{LONG}</p>'),
        ]
    )

    chapters = read_book(path).chapters

    assert [(c.chapter_number, c.title) for c in chapters] == [
        (7, "Chapter Seven"),
        (2, "Untitled heading"),
        (3, "c.xhtml"),
        (4, "Fallback title"),
    ]


def test_read_book_follows_spine_not_manifest_order(make_epub: EpubFactory) -> None:
    path = make_epub(
        [_chapter("b.xhtml", "Second"), _chapter("a.xhtml", "First")],
        spine=["a.xhtml", "b.xhtml"],
    )

    assert [c.title for c in read_chapters(path)] == ["First", "Second"]


def test_read_book_skips_navigation_document_in_spine(make_epub: EpubFactory) -> None:
    path = make_epub(
        [_chapter("ch1.xhtml", "One", toc="One")], spine=["nav", "ch1.xhtml"]
    )

    book = read_book(path)

    assert [(d.kind, d.narrate) for d in book.decisions] == [
        (MatterKind.TOC, False),
        (MatterKind.BODY, True),
    ]
    assert [c.title for c in book.chapters] == ["One"]


def test_read_book_titles_headingless_page_from_toc(make_epub: EpubFactory) -> None:
    path = make_epub([Page("ch1.xhtml", f"<p>{LONG}</p>", toc="Rozdział pierwszy")])

    assert [c.title for c in read_chapters(path)] == ["Rozdział pierwszy"]


def test_read_book_skips_pages_from_guide_and_non_linear_spine(
    make_epub: EpubFactory,
) -> None:
    path = make_epub(
        [
            _chapter("legal.xhtml", "Legalese"),
            _chapter("ch1.xhtml", "One"),
            _chapter("popup.xhtml", "Popup", linear=False),
            _chapter("ch2.xhtml", "Two"),
        ],
        guide=[{"href": "legal.xhtml", "title": "Legal", "type": "copyright-page"}],
    )

    book = read_book(path)

    assert [d.kind for d in book.decisions] == [
        MatterKind.COPYRIGHT,
        MatterKind.BODY,
        MatterKind.AUXILIARY,
        MatterKind.BODY,
    ]
    assert [c.title for c in book.chapters] == ["One", "Two"]


def test_read_book_honours_bodymatter_landmark(make_epub: EpubFactory) -> None:
    pages = [
        _chapter("preface.xhtml", "Preface"),
        Page("motto.xhtml", "<p>To be or not to be.</p>"),
        _chapter("ch1.xhtml", "One"),
    ]
    guide = [{"href": "ch1.xhtml", "title": "Start", "type": "text"}]

    assert [c.title for c in read_chapters(make_epub(pages))] == [
        "Preface",
        "motto.xhtml",
        "One",
    ]
    assert [c.title for c in read_chapters(make_epub(pages, guide=guide))] == [
        "Preface",
        "One",
    ]


def test_read_book_narrates_body_only_without_note_markers(
    make_epub: EpubFactory,
) -> None:
    path = make_epub(
        [
            Page(
                "ch1.xhtml",
                f"<h1>One</h1><p>The war ended<sup>1</sup>. {LONG}</p>"
                '<aside epub:type="footnote"><p>1. A footnote.</p></aside>',
                head_title="Book Title",
            )
        ]
    )

    content = read_chapters(path)[0].content

    assert content.startswith("One\nThe war ended. word")
    assert "footnote" not in content
    assert "Book Title" not in content


@pytest.fixture
def dedicated_book(make_epub: EpubFactory) -> Path:
    """A book with a cover, a dedication and two chapters."""
    return make_epub(
        [
            Page("cover.xhtml", "<img src='cover.jpg'/>"),
            Page("dedykacja.xhtml", "<p>Dla mamy</p>"),
            _chapter("ch1.xhtml", "Chapter 1"),
            _chapter("ch2.xhtml", "Chapter 2"),
        ]
    )


@pytest.mark.parametrize(
    ("options", "titles"),
    [
        (FilterOptions(), ["Chapter 1", "Chapter 2"]),
        (
            FilterOptions(skip=DEFAULT_SKIP - {MatterKind.DEDICATION}),
            ["dedykacja.xhtml", "Chapter 1", "Chapter 2"],
        ),
        (
            FilterOptions(include=("^dedyk",)),
            ["dedykacja.xhtml", "Chapter 1", "Chapter 2"],
        ),
        (FilterOptions(exclude=("chapter 2",)), ["Chapter 1"]),
        (FilterOptions(include=("chapter",), exclude=("chapter 2",)), ["Chapter 1"]),
        (FilterOptions(include=(".*",)), ["dedykacja.xhtml", "Chapter 1", "Chapter 2"]),
    ],
)
def test_read_book_applies_filter_options(
    dedicated_book: Path, options: FilterOptions, titles: list[str]
) -> None:
    assert [c.title for c in read_chapters(dedicated_book, options)] == titles


def test_read_book_explains_overrides(dedicated_book: Path) -> None:
    options = FilterOptions(include=("dedyk",), exclude=("chapter 2",))

    decisions = read_book(dedicated_book, options).decisions

    assert [(d.position, d.kind, d.narrate) for d in decisions] == [
        (1, MatterKind.EMPTY, False),
        (2, MatterKind.DEDICATION, True),
        (3, MatterKind.BODY, True),
        (4, MatterKind.BODY, False),
    ]
    assert decisions[1].reason.endswith("included by 'dedyk'")
    assert decisions[3].reason.endswith("excluded by 'chapter 2'")
    assert decisions[2].word_count == 202


def test_load_documents_reads_raw_body_markup() -> None:
    book = epub.EpubBook()
    item = epub.EpubHtml(uid="thanks", file_name="Text/thanks.xhtml")
    item.content = _html(f"<p>{LONG}</p>", 'epub:type="acknowledgments"')
    book.add_item(item)
    book.spine = [item]

    documents = load_documents(book)

    assert classify_documents(documents)[0].kind is MatterKind.ACKNOWLEDGMENTS


def test_load_documents_falls_back_to_manifest_order_without_spine() -> None:
    book = epub.EpubBook()
    for name in ("Text/b.xhtml", "Text/a.xhtml"):
        item = epub.EpubHtml(uid=name, file_name=name)
        item.content = _html("<p>Text</p>")
        book.add_item(item)

    assert [d.file_name for d in load_documents(book)] == [
        "Text/b.xhtml",
        "Text/a.xhtml",
    ]


def test_load_documents_collects_toc_labels_and_landmarks() -> None:
    book = epub.EpubBook()
    names = ("Text/p.xhtml", "Text/c.xhtml", "Text/d.xhtml")
    for name in names:
        item = epub.EpubHtml(uid=name, file_name=name)
        item.content = _html("<p>Text</p>")
        book.add_item(item)
    nav = epub.EpubNav(file_name="Text/nav.xhtml")
    nav.content = _html(
        '<nav epub:type="landmarks"><ol>'
        '<li><a epub:type="bodymatter" href="c.xhtml#start">Start</a></li>'
        '<li><a epub:type="index" href="d.xhtml">Index</a></li>'
        "</ol></nav>"
    )
    book.add_item(nav)
    book.add_item(epub.EpubNcx(file_name="ncx/toc.ncx"))
    book.spine = list(names)
    book.toc = [
        (
            epub.Section("Part", "Text/p.xhtml"),
            [
                epub.Link("Text/c.xhtml#x", "Fragment", "l1"),
                epub.Link("Text/c.xhtml", "Whole", "l2"),
            ],
        ),
        epub.Link("../Text/d.xhtml", "Relative to NCX", "l3"),
    ]
    book.guide = [{"href": "Text/d.xhtml#i", "title": "Index", "type": "index"}]

    documents = load_documents(book)

    assert [d.toc_label for d in documents] == ["Part", "Whole", "Relative to NCX"]
    assert documents[1].references == (Reference("bodymatter", partial=True),)
    assert set(documents[2].references) == {
        Reference("index", partial=True),
        Reference("index"),
    }


def _epub_with_metadata(path: Path, *, epub3_cover: bool) -> Path:
    """Write an EPUB with Dublin Core metadata and a cover image."""
    book = epub.EpubBook()
    book.set_identifier("meta")
    book.set_title("Tytuł")
    book.set_language("pl")
    book.add_author("Jan Kowalski")
    book.add_author("Anna Nowak")
    if epub3_cover:
        book.set_cover("cover.png", b"\x89PNG data", create_page=False)
    else:
        image = epub.EpubImage(
            uid="cover-id", file_name="cover.jpg", media_type="image/jpeg"
        )
        image.content = b"\xff\xd8 data"
        book.add_item(image)
        book.add_metadata(None, "meta", "", {"name": "cover", "content": "cover-id"})
    chapter = epub.EpubHtml(title="One", file_name="ch1.xhtml")
    chapter.content = f"<html><body><h1>One</h1><p>{LONG}</p></body></html>"
    book.add_item(chapter)
    book.spine = [chapter]
    book.add_item(epub.EpubNcx())
    epub.write_epub(str(path), book)
    return path


@pytest.mark.parametrize(
    ("epub3_cover", "cover"),
    [(True, (b"\x89PNG data", "image/png")), (False, (b"\xff\xd8 data", "image/jpeg"))],
)
def test_read_book_reads_epub_metadata_and_cover(
    tmp_path: Path, epub3_cover: bool, cover: tuple[bytes, str]
) -> None:
    path = _epub_with_metadata(tmp_path / "meta.epub", epub3_cover=epub3_cover)

    metadata = read_book(path).metadata

    assert metadata.title == "Tytuł"
    assert metadata.authors == ("Jan Kowalski", "Anna Nowak")
    assert metadata.language == "pl"
    assert metadata.cover is not None
    assert (metadata.cover.data, metadata.cover.mime_type) == cover


def _add_encryption(path: Path, uri: str) -> Path:
    """Add an ``encryption.xml`` encrypting ``uri`` to an EPUB."""
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(
            "META-INF/encryption.xml",
            '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<EncryptedData><CipherData>"
            f'<CipherReference URI="{uri}"/></CipherData></EncryptedData></encryption>',
        )
    return path


def test_read_book_rejects_drm_protected_epub(epub_file: Path) -> None:
    _add_encryption(epub_file, "EPUB/intro.xhtml")

    with pytest.raises(UnreadableBookError, match="DRM"):
        read_book(epub_file)


def test_read_book_accepts_epub_with_obfuscated_fonts(epub_file: Path) -> None:
    _add_encryption(epub_file, "EPUB/fonts/serif.otf")

    assert [c.title for c in read_book(epub_file).chapters] == ["Beginning", "The End"]


def test_read_book_rejects_broken_epub(tmp_path: Path) -> None:
    path = tmp_path / "broken.epub"
    path.write_bytes(b"not a zip")

    with pytest.raises(UnreadableBookError, match="broken.epub"):
        read_book(path)
