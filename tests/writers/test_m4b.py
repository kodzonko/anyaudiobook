"""Tests for writing an M4B audiobook with chapter markers, using real ffmpeg."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.mp4 import MP4, MP4Cover

from anyaudiobook import (
    AnyAudiobookError,
    BookMetadata,
    CoverImage,
    M4bWriter,
    MissingToolError,
)
from anyaudiobook.writers import Track
from anyaudiobook.writers.m4b import duration, ffmetadata, m4b_path
from tests.builders import FakeEngine, silent_mp3
from tests.conftest import ChapterFactory


def _probe_chapters(path: Path) -> list[tuple[str, float]]:
    """Return each chapter's title and start time, read by ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        pytest.skip("ffprobe is not installed")
    output = subprocess.run(
        [ffprobe, "-v", "error", "-show_chapters", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [
        (chapter["tags"]["title"], float(chapter["start_time"]))
        for chapter in json.loads(output)["chapters"]
    ]


@pytest.mark.usefixtures("ffmpeg")
def test_m4b_writer_joins_chapters_with_markers_and_tags(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    chapters = [
        make_chapter(1, "Opening = start", "a" * 100),
        make_chapter(2, "Closing; end", "b" * 250),
    ]
    metadata = BookMetadata(
        title="Book: Title",
        authors=("Jane Doe",),
        cover=CoverImage(b"\xff\xd8jpeg", "image/jpeg"),
    )

    (path,) = M4bWriter().write(chapters, metadata, tmp_path / "out", fake_engine)

    assert path == tmp_path / "out" / "Book Title.m4b"
    chapters_found = _probe_chapters(path)
    assert [title for title, _ in chapters_found] == ["Opening = start", "Closing; end"]
    assert chapters_found[1][1] == pytest.approx(FakeEngine.seconds("a" * 100), abs=0.1)
    tags = MP4(path).tags
    assert tags is not None
    assert tags["\xa9nam"] == ["Book: Title"]
    assert tags["\xa9ART"] == ["Jane Doe"]
    assert tags["stik"] == [2]
    (cover,) = tags["covr"]
    assert (bytes(cover), cover.imageformat) == (b"\xff\xd8jpeg", MP4Cover.FORMAT_JPEG)


@pytest.mark.usefixtures("ffmpeg")
def test_m4b_writer_writes_to_an_explicit_file(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    target = tmp_path / "nested" / "my book.m4b"

    (path,) = M4bWriter(bitrate="32k").write(
        [make_chapter()],
        BookMetadata(cover=CoverImage(b"png", "image/png")),
        target,
        fake_engine,
    )

    assert path == target
    tags = MP4(path).tags
    assert tags is not None
    assert tags["\xa9alb"] == ["Audiobook"]
    assert tags["covr"][0].imageformat == MP4Cover.FORMAT_PNG


@pytest.mark.usefixtures("no_tools")
def test_m4b_writer_checks_for_ffmpeg_before_narrating(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    with pytest.raises(MissingToolError, match="ffmpeg"):
        M4bWriter().write([make_chapter()], BookMetadata(), tmp_path, fake_engine)
    assert fake_engine.texts == []


def test_m4b_writer_reports_ffmpeg_failures(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    broken = tmp_path / "ffmpeg"
    broken.write_text("#!/bin/sh\necho 'Invalid data found' >&2\nexit 1\n")
    broken.chmod(0o755)

    with pytest.raises(AnyAudiobookError, match="Invalid data found"):
        M4bWriter(ffmpeg=str(broken)).write(
            [make_chapter()], BookMetadata(), tmp_path / "out", fake_engine
        )


def test_ffmetadata_escapes_values_and_times_chapters(
    tmp_path: Path, make_chapter: ChapterFactory
) -> None:
    tracks = []
    for number, seconds in ((1, 1.0), (2, 2.0)):
        path = tmp_path / f"{number}.mp3"
        path.write_bytes(silent_mp3(seconds))
        tracks.append(Track(make_chapter(number, f"Part #{number}\\x"), path))

    text = ffmetadata(tracks, BookMetadata(title="A=B", authors=("C;D",)))

    lines = text.splitlines()
    assert lines[:4] == [";FFMETADATA1", "title=A\\=B", "album=A\\=B", "artist=C\\;D"]
    assert "title=Part \\#1\\\\x" in lines
    starts = [int(line[6:]) for line in lines if line.startswith("START=")]
    assert starts[0] == 0
    assert starts[1] == pytest.approx(1000, abs=30)


def test_duration_rejects_files_that_are_not_audio(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not audio")

    with pytest.raises(AnyAudiobookError, match="notes.txt"):
        duration(path)


@pytest.mark.parametrize(
    ("output", "title", "expected"),
    [
        ("book.M4B", "Ignored", "book.M4B"),
        ("dir", "Title/With:Chars", "dir/TitleWithChars.m4b"),
        ("dir", None, "dir/Audiobook.m4b"),
    ],
)
def test_m4b_path(output: str, title: str | None, expected: str) -> None:
    assert m4b_path(Path(output), BookMetadata(title=title)) == Path(expected)
