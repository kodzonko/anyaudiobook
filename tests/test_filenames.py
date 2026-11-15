"""Tests for chapter file naming."""

import pytest

from anyaudiobook.filenames import (
    MAX_TITLE_LENGTH,
    book_filename,
    chapter_filename,
    clean_title,
    parse_chapter_filename,
)
from anyaudiobook.models import BookMetadata
from tests.conftest import ChapterFactory


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Plain", "Plain"),
        ('A\\b/c:d*e?f"g<h>i|j', "Abcdefghij"),
        ("  padded  ", "padded"),
    ],
)
def test_clean_title_strips_invalid_characters(title: str, expected: str) -> None:
    assert clean_title(title) == expected


def test_clean_title_truncates_long_titles() -> None:
    cleaned = clean_title("x" * 200)
    assert len(cleaned) == MAX_TITLE_LENGTH
    assert cleaned.endswith("...")


@pytest.mark.parametrize(
    ("number", "total", "expected"),
    [(3, 9, "3. Title.mp3"), (3, 12, "03. Title.mp3"), (42, 120, "042. Title.mp3")],
)
def test_chapter_filename_pads_to_total_width(
    make_chapter: ChapterFactory, number: int, total: int, expected: str
) -> None:
    assert chapter_filename(make_chapter(chapter_number=number), total) == expected


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("04. Some Title", (4, "Some Title")),
        ("12.No space", (12, "No space")),
        ("1. A. B", (1, "A. B")),
    ],
)
def test_parse_chapter_filename(stem: str, expected: tuple[int, str]) -> None:
    assert parse_chapter_filename(stem) == expected


@pytest.mark.parametrize("stem", ["Intro", "x1. Title", ". Title"])
def test_parse_chapter_filename_rejects_unnumbered_stems(stem: str) -> None:
    with pytest.raises(ValueError, match="Not a numbered chapter"):
        parse_chapter_filename(stem)


def test_chapter_filename_round_trips(make_chapter: ChapterFactory) -> None:
    name = chapter_filename(make_chapter(chapter_number=5, title="Round: Trip"), 10)
    assert parse_chapter_filename(name.removesuffix(".mp3")) == (5, "Round Trip")


def test_chapter_filename_uses_the_given_extension(
    make_chapter: ChapterFactory,
) -> None:
    assert chapter_filename(make_chapter(3, "Three"), 12, ".wav") == "03. Three.wav"


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            BookMetadata(title="Lorem Ipsum", authors=("Jane Doe",)),
            "Jane Doe - Lorem Ipsum",
        ),
        (
            BookMetadata(title="Dune", authors=("Frank Herbert", "Brian Herbert")),
            "Frank Herbert, Brian Herbert - Dune",
        ),
        (BookMetadata(title="Untitled Notes"), "Untitled Notes"),
        (BookMetadata(authors=("Jane Doe",)), "Jane Doe"),
        (BookMetadata(), "Audiobook"),
        (
            BookMetadata(title='What? A "Story":\n Part 1/2', authors=("Jane\tDoe",)),
            "Jane Doe - What A Story Part 12",
        ),
        (
            BookMetadata(title="And then...", authors=("Jane Doe",)),
            "Jane Doe - And then",
        ),
        (BookMetadata(title="..."), "Audiobook"),
    ],
    ids=[
        "author-title",
        "authors",
        "no-author",
        "no-title",
        "nothing",
        "unsafe",
        "dots",
        "only-dots",
    ],
)
def test_book_filename_is_author_dash_title_and_safe(
    metadata: BookMetadata, expected: str
) -> None:
    assert book_filename(metadata) == expected


def test_book_filename_caps_its_length() -> None:
    name = book_filename(BookMetadata(title="x" * 500, authors=("Jane Doe",)))

    assert len(name) <= MAX_TITLE_LENGTH
    assert name.startswith("Jane Doe - xxx")
