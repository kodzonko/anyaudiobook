"""Tests for chapter file naming."""

import pytest

from anyaudiobook.filenames import (
    MAX_TITLE_LENGTH,
    chapter_filename,
    clean_title,
    parse_chapter_filename,
)
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
