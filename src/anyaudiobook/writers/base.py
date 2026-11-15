"""The writer interface: how narrated chapters become an audiobook."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import anyio

from anyaudiobook.errors import AnyAudiobookError
from anyaudiobook.models import BookContent, BookMetadata
from anyaudiobook.progress import Packaging, ProgressCallback, ignore
from anyaudiobook.tts import SpeechEngine, synthesize_chapters


@dataclass(frozen=True, slots=True)
class Track:
    """A narrated chapter and the audio file holding it."""

    chapter: BookContent
    path: Path


class AudiobookWriter(ABC):
    """Packages narrated chapters as an audiobook of one format.

    :meth:`write` is a template shared by every format: check that the
    tools needed are installed, narrate the chapters into the directory
    :meth:`work_dir` provides, then :meth:`package` the files. Formats
    differ only in those three steps; :data:`anyaudiobook.writers.WRITERS`
    picks one by name.
    """

    format_name: ClassVar[str]
    """The format's name, e.g. ``m4b``."""
    description: ClassVar[str]
    """What the format writes, as offered in the TUI's list of formats."""
    file_suffix: ClassVar[str | None] = None
    """Extension of the single file the format writes, e.g. ``.m4b``; None
    when it writes a folder of files."""

    def write(
        self,
        chapters: Sequence[BookContent],
        metadata: BookMetadata,
        output: Path,
        engine: SpeechEngine,
        concurrency: int = 10,
        progress: ProgressCallback = ignore,
    ) -> list[Path]:
        """Narrate ``chapters`` with ``engine`` and package them at ``output``.

        Args:
            chapters: The chapters to narrate, in order.
            metadata: Title, authors and cover to tag the files with.
            output: Where to write; what it means depends on the format.
            engine: The speech engine to narrate with.
            concurrency: Most chapters narrated at the same time.
            progress: Told how narration goes, and when packaging starts.

        Returns:
            The files written.

        Raises:
            AnyAudiobookError: If there is nothing to narrate.
            MissingToolError: If a tool the format needs is not installed;
                checked before any narration starts.
        """
        if not chapters:
            raise AnyAudiobookError("Nothing to narrate: every chapter was skipped")
        self.check()
        output = Path(output)
        with self.work_dir(output) as work_dir:
            paths = anyio.run(
                synthesize_chapters, chapters, work_dir, engine, concurrency, progress
            )
            tracks = [
                Track(chapter, path)
                for chapter, path in zip(chapters, paths, strict=True)
            ]
            progress(Packaging(output_format=self.format_name))
            return self.package(tracks, metadata, output)

    def check(self) -> None:
        """Fail early if something the format needs is missing; no-op by default."""

    @abstractmethod
    def work_dir(self, output: Path) -> AbstractContextManager[Path]:
        """Return a context providing the directory to narrate chapters into."""

    @abstractmethod
    def package(
        self, tracks: Sequence[Track], metadata: BookMetadata, output: Path
    ) -> list[Path]:
        """Turn the narrated chapters into the final files and return them."""
