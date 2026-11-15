"""Tests for writing one tagged MP3 file per chapter."""

from pathlib import Path

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

from anyaudiobook.errors import AnyAudiobookError
from anyaudiobook.models import BookMetadata, CoverImage
from anyaudiobook.writers.mp3 import Mp3Writer
from tests.builders import FakeEngine
from tests.conftest import ChapterFactory


def test_mp3_writer_narrates_and_tags_every_chapter(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    chapters = [
        make_chapter(1, "Opening", "First."),
        make_chapter(2, "Closing", "End."),
    ]
    metadata = BookMetadata(
        title="Book",
        authors=("Jane Doe", "John Roe"),
        cover=CoverImage(b"png-bytes", "image/png"),
    )

    paths = Mp3Writer().write(chapters, metadata, tmp_path / "out", fake_engine)

    assert [p.name for p in paths] == ["1. Opening.mp3", "2. Closing.mp3"]
    assert fake_engine.texts == ["First.", "End."]
    tags = EasyID3(str(paths[1]))
    assert tags["artist"] == ["Jane Doe, John Roe"]
    assert tags["album"] == ["Book"]
    assert (tags["title"], tags["tracknumber"]) == (["Closing"], ["2"])
    (apic,) = ID3(str(paths[0])).getall("APIC")
    assert (apic.mime, apic.data) == ("image/png", b"png-bytes")


def test_writer_refuses_to_write_an_empty_book(
    tmp_path: Path, fake_engine: FakeEngine
) -> None:
    with pytest.raises(AnyAudiobookError, match="Nothing to narrate"):
        Mp3Writer().write([], BookMetadata(), tmp_path, fake_engine)
    assert fake_engine.texts == []
