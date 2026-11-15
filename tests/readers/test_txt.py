"""Tests for plain text books, read from real files."""

from pathlib import Path

import pytest

from anyaudiobook.matter.models import MatterKind
from anyaudiobook.readers.txt import decode_text, paragraphs, strip_gutenberg
from anyaudiobook.selection import read_book

WRAPPED = """\
It was a dark and stormy night; the rain fell in torrents, except at
occasional intervals, when it was checked by a violent gust of wind
which swept up the streets."""

BOOK = f"""\
THE TITLE
by Jane Doe

Copyright © 2020 Jane Doe. All rights reserved.
ISBN 978-0-00-000000-0

Chapter 1
{WRAPPED}

Second paragraph, hyphen-
ated across lines.

CHAPTER II. The Return

{" ".join(["She came back to the house."] * 40)}

Acknowledgments

Thanks to everyone.
"""


@pytest.fixture
def txt_book(tmp_path: Path) -> Path:
    """A UTF-8 text book with front matter, two chapters and thanks."""
    path = tmp_path / "book.txt"
    path.write_text(BOOK, encoding="utf-8")
    return path


def test_read_book_splits_text_into_chapters_and_skips_matter(txt_book: Path) -> None:
    book = read_book(txt_book)

    assert [(d.kind, d.title) for d in book.decisions] == [
        (MatterKind.COPYRIGHT, "section-001"),
        (MatterKind.BODY, "Chapter 1"),
        (MatterKind.BODY, "CHAPTER II. The Return"),
        (MatterKind.ACKNOWLEDGMENTS, "Acknowledgments"),
    ]
    first = book.chapters[0].content
    assert first.startswith("Chapter 1\nIt was a dark and stormy night; the rain")
    assert "occasional intervals, when" in first
    assert first.endswith("Second paragraph, hyphenated across lines.")


def test_read_book_decodes_legacy_polish_encodings(tmp_path: Path) -> None:
    text = "Rozdział pierwszy\n\n" + "Zażółć gęślą jaźń, powiedział Łukasz. " * 30
    path = tmp_path / "ksiazka.txt"
    path.write_bytes(text.encode("cp1250"))

    chapter = read_book(path).chapters[0]

    assert chapter.title == "Rozdział pierwszy"
    assert "Zażółć gęślą jaźń" in chapter.content


@pytest.mark.parametrize(
    ("data", "text"),
    [
        ("Zażółć\r\ngęślą".encode(), "Zażółć\ngęślą"),
        ("﻿BOM\rline".encode(), "BOM\nline"),
    ],
)
def test_decode_text_handles_utf8_and_newlines(data: bytes, text: str) -> None:
    assert decode_text(data) == text


def test_strip_gutenberg_keeps_only_the_book() -> None:
    text = (
        "Licence header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
        "The book.\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nLicence footer"
    )

    assert strip_gutenberg(text).strip() == "The book."
    assert strip_gutenberg("No markers.") == "No markers."


def test_paragraphs_split_on_indentation_and_long_lines() -> None:
    indented = "  First paragraph\nwraps here.\n  Second paragraph."
    long_lines = "\n".join(["A whole paragraph on one line. " * 4] * 2)

    assert list(paragraphs(indented)) == [
        "First paragraph wraps here.",
        "Second paragraph.",
    ]
    assert len(list(paragraphs(long_lines))) == 2
    assert list(paragraphs("Prologue\nIt began.\n\n\n")) == ["Prologue", "It began."]
