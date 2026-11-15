"""Tests for PDF books, generated with reportlab and read back for real."""

from pathlib import Path

import pymupdf
import pytest

from anyaudiobook.errors import UnreadableBookError
from anyaudiobook.matter.models import MatterKind
from anyaudiobook.readers.pdf import PdfReader
from anyaudiobook.selection import read_book, select_chapters
from tests.builders import PdfChapter, write_image_pdf, write_pdf

LONG = " ".join(["The story goes on and on without end."] * 100)
"""About two pages of text."""

CHAPTERS = [
    PdfChapter(
        "Copyright",
        ["Copyright © 2020 Jane Doe. All rights reserved. ISBN 978-0-00-000000-0"],
    ),
    PdfChapter(
        "Chapter 1",
        [
            [
                "It was the best of times, it was the worst of times, it was the",
                "age of wisdom, it was the age of foolish-",
                "ness, it was the epoch of belief.^1",
            ],
            LONG,
        ],
        footnote="1 A footnote explaining the epoch.",
    ),
    PdfChapter("Chapter 2", [LONG]),
    PdfChapter("Acknowledgments", ["Thanks to everyone who helped."]),
]


@pytest.fixture
def pdf_book(tmp_path: Path) -> Path:
    """A PDF with an outline, running headers, page numbers and a footnote."""
    return write_pdf(tmp_path / "book.pdf", CHAPTERS)


def test_read_book_splits_pdf_by_outline_and_skips_matter(pdf_book: Path) -> None:
    book = read_book(pdf_book)

    assert [(d.kind, d.title, d.file_name) for d in book.decisions] == [
        (MatterKind.COPYRIGHT, "Copyright", "page 1"),
        (MatterKind.BODY, "Chapter 1", "pages 2-3"),
        (MatterKind.BODY, "Chapter 2", "pages 4-5"),
        (MatterKind.ACKNOWLEDGMENTS, "Acknowledgments", "page 6"),
    ]
    assert (book.metadata.title, book.metadata.authors) == ("Test PDF", ("Jane Doe",))


def test_read_book_cleans_pdf_layout_out_of_the_narration(pdf_book: Path) -> None:
    chapter = read_book(pdf_book).chapters[0].content

    assert chapter.startswith(
        "Chapter 1\nIt was the best of times, it was the worst of times, it was the "
        "age of wisdom, it was the age of foolishness, it was the epoch of belief.\n"
        "The story goes on"
    )
    assert "Test PDF" not in chapter  # running header
    assert "footnote" not in chapter
    assert not any(line.strip().isdigit() for line in chapter.splitlines())
    # Paragraphs only break where sentences end, also across pages.
    assert all(line.endswith(".") for line in chapter.splitlines()[1:])


def test_read_book_joins_words_hyphenated_across_pages(tmp_path: Path) -> None:
    lines = [f"filler words on line number {n} and" for n in range(32)]
    lines += ["then the word contin-", "ued on the next page."]
    path = write_pdf(tmp_path / "flow.pdf", [PdfChapter("Chapter 1", [lines])])

    (chapter,) = read_book(path).chapters

    assert chapter.content.endswith(
        "line number 31 and then the word continued on the next page."
    )
    assert chapter.content.count("\n") == 1


def test_read_book_splits_pdf_without_outline_at_big_headings(tmp_path: Path) -> None:
    path = write_pdf(tmp_path / "plain.pdf", CHAPTERS, outline=False)

    book = read_book(path)

    assert [d.title for d in book.decisions] == [
        "Copyright",
        "Chapter 1",
        "Chapter 2",
        "Acknowledgments",
    ]
    assert [c.title for c in book.chapters] == ["Chapter 1", "Chapter 2"]


def test_pdf_reader_outline_depth_and_unlisted_front_matter(tmp_path: Path) -> None:
    chapters = [PdfChapter("Title Page", ["A Book"], in_outline=False), *CHAPTERS[1:3]]
    path = write_pdf(tmp_path / "book.pdf", chapters)

    book = select_chapters(PdfReader(outline_depth=1).read(path))

    assert [(d.kind, d.title) for d in book.decisions] == [
        (MatterKind.TITLE_PAGE, "Title Page"),
        (MatterKind.BODY, "Chapter 1"),
        (MatterKind.BODY, "Chapter 2"),
    ]


def test_pdf_reader_uses_first_page_image_as_cover(tmp_path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False)
    page.insert_image(page.rect, pixmap=pixmap)
    page.insert_text((72, 72), "Cover text " * 10)
    document.new_page().insert_text((72, 72), "Chapter text " * 10)
    path = tmp_path / "cover.pdf"
    document.save(path)

    with_cover = read_book(path).metadata.cover
    without = PdfReader(cover=False).read(path).metadata.cover

    assert with_cover is not None and with_cover.mime_type == "image/jpeg"
    assert with_cover.data[:2] == b"\xff\xd8"
    assert without is None


def test_read_book_rejects_scanned_pdf(tmp_path: Path) -> None:
    with pytest.raises(UnreadableBookError, match="OCR"):
        read_book(write_image_pdf(tmp_path / "scan.pdf"))


def test_read_book_rejects_password_protected_pdf(tmp_path: Path) -> None:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Secret text " * 20)
    path = tmp_path / "locked.pdf"
    document.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # ty: ignore[missing-attribute]
        user_pw="user",
        owner_pw="owner",
    )

    with pytest.raises(UnreadableBookError, match="password"):
        read_book(path)


def test_read_book_rejects_files_that_are_not_pdf(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_text("plain text, not a PDF")

    with pytest.raises(UnreadableBookError, match="fake.pdf"):
        read_book(path)
