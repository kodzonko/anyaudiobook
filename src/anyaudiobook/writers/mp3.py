"""One tagged MP3 file per chapter."""

from collections.abc import Sequence
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

from anyaudiobook.metadata import add_metadata
from anyaudiobook.models import BookMetadata
from anyaudiobook.writers.base import AudiobookWriter, Track


class Mp3Writer(AudiobookWriter):
    """Writes ``NN. Title.mp3`` files into a directory, with ID3 tags.

    ``output`` is the directory. Each file is tagged with the book title as
    album, the authors as artist, the chapter title, its track number and
    the cover. The speech engine must produce MP3 files.
    """

    format_name = "mp3"

    def work_dir(self, output: Path) -> AbstractContextManager[Path]:
        """Narrate straight into the output directory."""
        return nullcontext(output)

    def package(
        self, tracks: Sequence[Track], metadata: BookMetadata, output: Path
    ) -> list[Path]:
        """Tag every chapter file."""
        for track in tracks:
            add_metadata(
                track.path,
                metadata.author,
                metadata.title or "",
                track.chapter.title,
                track.chapter.chapter_number,
                metadata.cover,
            )
        return [track.path for track in tracks]
