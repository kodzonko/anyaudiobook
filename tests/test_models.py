"""Tests for the shared data models."""

from pathlib import Path

import pytest

from anyaudiobook import BookMetadata, CoverImage


@pytest.mark.parametrize(
    ("name", "mime_type"),
    [("cover.png", "image/png"), ("cover.JPG", "image/jpeg"), ("cover", "image/jpeg")],
)
def test_cover_image_from_file_judges_type_by_extension(
    tmp_path: Path, name: str, mime_type: str
) -> None:
    path = tmp_path / name
    path.write_bytes(b"data")

    assert CoverImage.from_file(path) == CoverImage(b"data", mime_type)


def test_book_metadata_updated_keeps_fields_the_override_leaves_unset() -> None:
    cover = CoverImage(b"x")
    book = BookMetadata(title="Book", authors=("A",), language="pl", cover=cover)

    updated = book.updated(BookMetadata(title="New", authors=("B", "C")))

    assert updated == BookMetadata(
        title="New", authors=("B", "C"), language="pl", cover=cover
    )
    assert updated.author == "B, C"
    assert book.updated(None) is book
