"""Tests for ID3 tagging, run against real files with mutagen."""

from pathlib import Path

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

from anyaudiobook.metadata import add_metadata, tag_chapters
from anyaudiobook.models import CoverImage


def _blank_mp3(path: Path) -> Path:
    """Write a file with no ID3 header to stand in for an MP3."""
    path.write_bytes(b"\x00" * 128)
    return path


@pytest.fixture
def mp3_file(tmp_path: Path) -> Path:
    """A blank MP3 file without tags."""
    return _blank_mp3(tmp_path / "01. Chapter.mp3")


def test_add_metadata_writes_tags(mp3_file: Path) -> None:
    add_metadata(mp3_file, "Jane Doe", "Book", "Chapter", 1)

    tags = EasyID3(str(mp3_file))
    assert tags["artist"] == ["Jane Doe"]
    assert tags["album"] == ["Book"]
    assert tags["title"] == ["Chapter"]
    assert tags["tracknumber"] == ["1"]


def test_add_metadata_overwrites_existing_tags(mp3_file: Path) -> None:
    add_metadata(mp3_file, "Old", "Old", "Old", 9)
    add_metadata(mp3_file, "New", "New", "New", 2)

    assert EasyID3(str(mp3_file))["artist"] == ["New"]


@pytest.mark.parametrize(
    ("suffix", "mime"), [(".jpg", "image/jpeg"), (".PNG", "image/png")]
)
def test_add_metadata_embeds_cover(
    mp3_file: Path, tmp_path: Path, suffix: str, mime: str
) -> None:
    cover = tmp_path / f"cover{suffix}"
    cover.write_bytes(b"image-bytes")

    add_metadata(mp3_file, "A", "B", "C", 1, cover)

    (apic,) = ID3(str(mp3_file)).getall("APIC")
    assert apic.mime == mime
    assert apic.data == b"image-bytes"


def test_tag_chapters_uses_file_names(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    first = _blank_mp3(tmp_path / "01. Opening.mp3")
    second = _blank_mp3(nested / "02. Closing.mp3")

    tag_chapters(tmp_path, "Jane Doe", "Book")

    assert EasyID3(str(first))["title"] == ["Opening"]
    assert EasyID3(str(second))["tracknumber"] == ["2"]


def test_tag_chapters_rejects_unnumbered_files(tmp_path: Path) -> None:
    _blank_mp3(tmp_path / "bonus.mp3")

    with pytest.raises(ValueError, match="bonus"):
        tag_chapters(tmp_path, "Jane Doe", "Book")


def test_add_metadata_replaces_cover_when_retagging(mp3_file: Path) -> None:
    add_metadata(mp3_file, "A", "B", "C", 1, CoverImage(b"old", "image/png"))
    add_metadata(mp3_file, "A", "B", "C", 1, CoverImage(b"new", "image/jpeg"))

    (apic,) = ID3(str(mp3_file)).getall("APIC")
    assert (apic.mime, apic.data) == ("image/jpeg", b"new")
