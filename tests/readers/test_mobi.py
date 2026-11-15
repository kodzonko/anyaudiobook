"""Tests for Kindle books, read from committed MOBI 7 and AZW3 files."""

from pathlib import Path

import pytest

from anyaudiobook import MatterKind, UnreadableBookError, read_book
from tests.conftest import FIXTURES


@pytest.mark.parametrize("name", ["book.mobi", "book.azw3"])
def test_read_book_reads_kindle_books(name: str) -> None:
    book = read_book(FIXTURES / name)

    assert [c.title for c in book.chapters] == [
        "Chapter 1. Beginnings",
        "Chapter 2. Endings",
    ]
    assert book.chapters[0].content.startswith("Chapter 1. Beginnings\nThe story")
    skipped = {d.kind for d in book.decisions if not d.narrate}
    assert {MatterKind.COPYRIGHT, MatterKind.ACKNOWLEDGMENTS} <= skipped
    assert (book.metadata.title, book.metadata.authors) == (
        "Kindle Test Book",
        ("Jane Doe",),
    )
    assert book.metadata.cover is not None
    assert book.metadata.cover.mime_type == "image/jpeg"


def test_read_book_splits_mobi7_at_its_ncx_entries() -> None:
    decisions = read_book(FIXTURES / "book.mobi").decisions

    assert [d.title for d in decisions] == [
        "Copyright",
        "Chapter 1. Beginnings",
        "Chapter 2. Endings",
        "Acknowledgments",
    ]


def test_read_book_rejects_broken_kindle_files(tmp_path: Path) -> None:
    path = tmp_path / "broken.azw3"
    path.write_bytes(b"BOOKMOBI" + bytes(100))

    with pytest.raises(UnreadableBookError, match="DRM"):
        read_book(path)
