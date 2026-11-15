"""Tests for Word DOCX documents, read from real files."""

from pathlib import Path

import pytest

from anyaudiobook import MatterKind, UnreadableBookError, read_book
from tests.builders import Para, write_docx

LONG = " ".join(["The story goes on."] * 60)


def test_read_book_uses_heading_styles_and_drops_footnotes(tmp_path: Path) -> None:
    path = write_docx(
        tmp_path / "book.docx",
        [
            Para("My Book", "Title"),
            Para("Copyright © 2020 Jane Doe. All rights reserved."),
            Para("Chapter 1", "Heading1"),
            Para(f"{LONG} The war ended.", footnote="A footnote about the war."),
            Para("A section", "Heading2"),
            Para(LONG),
            Para("Chapter 2", "Heading1"),
            Para(LONG),
        ],
        title="My Book",
    )

    book = read_book(path)

    assert (book.metadata.title, book.metadata.authors) == ("My Book", ("Jane Doe",))
    assert [(d.kind, d.title) for d in book.decisions] == [
        (MatterKind.COPYRIGHT, "My Book"),
        (MatterKind.BODY, "Chapter 1"),
        (MatterKind.BODY, "Chapter 2"),
        (MatterKind.NOTES, "section-004"),
    ]
    first = book.chapters[0].content
    assert "The war ended.\nA section" in first
    assert "[1]" not in first
    assert "footnote" not in first


def test_read_book_finds_chapters_in_docx_without_heading_styles(
    tmp_path: Path,
) -> None:
    path = write_docx(
        tmp_path / "plain.docx",
        [Para("Rozdział 1"), Para(LONG), Para("Rozdział 2"), Para(LONG)],
        title=None,
        author=None,
    )

    book = read_book(path)

    assert [c.title for c in book.chapters] == ["Rozdział 1", "Rozdział 2"]
    assert book.metadata.title is None


def test_read_book_rejects_broken_docx(tmp_path: Path) -> None:
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip file")

    with pytest.raises(UnreadableBookError, match="broken.docx"):
        read_book(path)
