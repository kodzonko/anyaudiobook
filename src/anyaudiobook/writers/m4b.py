"""A single M4B audiobook file with chapter markers, built with ffmpeg."""

import tempfile
from collections.abc import Generator, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import cast

import mutagen
from mutagen.mp4 import MP4, MP4Cover, MP4Tags

from anyaudiobook.errors import AnyAudiobookError
from anyaudiobook.filenames import clean_title
from anyaudiobook.models import BookMetadata
from anyaudiobook.tools import require_tool, run_tool
from anyaudiobook.writers.base import AudiobookWriter, Track

AUDIOBOOK_MEDIA_KIND = 2
"""iTunes ``stik`` value marking a file as an audiobook."""

_FFMETADATA_SPECIAL = str.maketrans({c: f"\\{c}" for c in "=;#\\\n"})
_FFMPEG_HINT = "Install it from https://ffmpeg.org (macOS: brew install ffmpeg)."


class M4bWriter(AudiobookWriter):
    """Writes one ``.m4b`` file (AAC audio in MP4) with a chapter per chapter.

    ``output`` is the ``.m4b`` file, or a directory to write
    ``<book title>.m4b`` into. Chapters are narrated into a temporary
    directory, joined and encoded by ffmpeg, then tagged (title, authors,
    cover, audiobook media kind) with mutagen. Needs ``ffmpeg``.
    """

    format_name = "m4b"

    def __init__(self, bitrate: str = "64k", ffmpeg: str | None = None) -> None:
        """Configure the encoding.

        Args:
            bitrate: AAC bitrate; 64k is plenty for speech.
            ffmpeg: Path to the ffmpeg program; looked up on ``PATH`` if None.
        """
        self.bitrate = bitrate
        self.ffmpeg = ffmpeg

    def check(self) -> None:
        """Make sure ffmpeg is installed before hours of narration start."""
        self.ffmpeg = self.ffmpeg or require_tool(
            "Writing M4B audiobooks", "ffmpeg", hint=_FFMPEG_HINT
        )

    def work_dir(self, output: Path) -> AbstractContextManager[Path]:
        """Narrate into a temporary directory, removed afterwards."""
        return _temporary_dir()

    def package(
        self, tracks: Sequence[Track], metadata: BookMetadata, output: Path
    ) -> list[Path]:
        """Join the chapters into one tagged M4B file with chapter markers."""
        target = m4b_path(output, metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        work_dir = tracks[0].path.parent
        playlist = work_dir / "chapters.txt"
        playlist.write_text(
            "".join(f"file '{_quote(track.path)}'\n" for track in tracks),
            encoding="utf-8",
        )
        chapters = work_dir / "chapters.ffmeta"
        chapters.write_text(ffmetadata(tracks, metadata), encoding="utf-8")
        run_tool(
            [
                self.ffmpeg or "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(playlist),
                "-i",
                str(chapters),
                "-map",
                "0:a",
                "-map_metadata",
                "1",
                "-map_chapters",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                self.bitrate,
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(target),
            ],
            "Encoding the M4B file with ffmpeg",
        )
        tag_m4b(target, metadata)
        return [target]


def m4b_path(output: Path, metadata: BookMetadata) -> Path:
    """Return the file to write: ``output`` itself, or a file named after the
    book inside it when ``output`` is not an ``.m4b`` path."""
    if output.suffix.lower() == ".m4b":
        return output
    return output / f"{clean_title(metadata.title or 'Audiobook')}.m4b"


def ffmetadata(tracks: Sequence[Track], metadata: BookMetadata) -> str:
    """Return an ffmpeg metadata file with one chapter per track.

    Chapter boundaries come from the duration of each track's audio.

    Raises:
        AnyAudiobookError: If a track's duration cannot be read.
    """
    title = _escape(metadata.title or "Audiobook")
    lines = [";FFMETADATA1", f"title={title}", f"album={title}"]
    if metadata.author:
        lines.append(f"artist={_escape(metadata.author)}")
    start = 0
    for track in tracks:
        end = start + round(duration(track.path) * 1000)
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={_escape(track.chapter.title)}",
        ]
        start = end
    return "\n".join(lines) + "\n"


def duration(path: Path) -> float:
    """Return the length of an audio file in seconds.

    Raises:
        AnyAudiobookError: If mutagen cannot read the file.
    """
    audio = mutagen.File(path)
    if audio is None or not getattr(audio, "info", None):
        raise AnyAudiobookError(f"Cannot read the length of {path}")
    return float(audio.info.length)


def tag_m4b(path: Path, metadata: BookMetadata) -> None:
    """Write title, authors, genre, media kind and cover tags to an M4B file."""
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    tags = cast(MP4Tags, audio.tags)
    title = metadata.title or "Audiobook"
    tags["\xa9nam"] = [title]
    tags["\xa9alb"] = [title]
    tags["\xa9gen"] = ["Audiobook"]
    tags["stik"] = [AUDIOBOOK_MEDIA_KIND]
    if metadata.author:
        tags["\xa9ART"] = [metadata.author]
        tags["aART"] = [metadata.author]
    if metadata.cover:
        image_format = (
            MP4Cover.FORMAT_PNG
            if metadata.cover.mime_type == "image/png"
            else MP4Cover.FORMAT_JPEG
        )
        tags["covr"] = [MP4Cover(metadata.cover.data, imageformat=image_format)]
    audio.save()


def _escape(value: str) -> str:
    """Escape a value for an ffmpeg metadata file."""
    return value.translate(_FFMETADATA_SPECIAL)


def _quote(path: Path) -> str:
    """Escape a path for an ffmpeg concat playlist (single-quoted)."""
    return str(path).replace("'", "'\\''")


@contextmanager
def _temporary_dir() -> Generator[Path]:
    """Yield a temporary directory, removed with everything in it on exit."""
    with tempfile.TemporaryDirectory(prefix="anyaudiobook-") as name:
        yield Path(name)
