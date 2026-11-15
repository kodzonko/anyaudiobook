"""Turn chapter text into speech.

Speech engines are interchangeable: anything with an ``audio_suffix`` and an
async ``synthesize(text, path, progress)`` method is a :class:`SpeechEngine`.
:class:`EdgeTTS`, Microsoft Edge's online voices, is the one built in.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import ClassVar, Protocol

import anyio
import edge_tts

from anyaudiobook.filenames import chapter_filename
from anyaudiobook.models import BookContent
from anyaudiobook.progress import (
    Advanced,
    ChapterNarrated,
    ChapterStarted,
    NarrationStarted,
    ProgressCallback,
    ignore,
)

TextProgress = Callable[[int], None]
"""Told how many characters of a text have been narrated so far."""


class SpeechEngine(Protocol):
    """Narrates text into an audio file."""

    @property
    def audio_suffix(self) -> str:
        """Extension of the files :meth:`synthesize` writes, e.g. ``.mp3``."""
        ...

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Narrate ``text`` and save the audio to ``output_path``.

        Engines that can tell how far they have got call ``progress`` with
        the number of characters narrated so far; others may never call it.
        """
        ...


@dataclass(frozen=True, slots=True)
class EdgeTTS:
    """Microsoft Edge's online text-to-speech voices; writes MP3 files.

    Args:
        voice: Voice short name, e.g. ``en-US-BrianNeural``; list them with
            ``uv run edge-tts --list-voices``.
        pitch: Pitch adjustment, e.g. ``-10Hz``.
        rate: Speed adjustment, e.g. ``+10%``.
        volume: Volume adjustment, e.g. ``-20%``.
    """

    voice: str
    pitch: str = "+0Hz"
    rate: str = "+0%"
    volume: str = "+0%"
    audio_suffix: ClassVar[str] = ".mp3"

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Narrate ``text`` into an MP3 file at ``output_path``.

        Progress is counted from the sentence boundaries the service sends
        along with the audio.
        """
        communicate = edge_tts.Communicate(
            text, self.voice, pitch=self.pitch, rate=self.rate, volume=self.volume
        )
        spoken = 0
        with output_path.open("wb") as audio:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.write(chunk.get("data", b""))
                elif progress is not None:
                    spoken += len(chunk.get("text", ""))
                    progress(spoken)


async def synthesize_chapters(
    chapters: Sequence[BookContent],
    output_dir: Path,
    engine: SpeechEngine,
    concurrency: int = 10,
    progress: ProgressCallback = ignore,
) -> list[Path]:
    """Narrate chapters concurrently, writing one audio file per chapter.

    Files are named ``NN. Title`` plus the engine's extension.

    Args:
        chapters: The chapters to narrate.
        output_dir: Directory for the audio files; created if missing.
        engine: The speech engine to narrate with.
        concurrency: Most chapters narrated at the same time.
        progress: Told when narration and each chapter start and finish, and
            how many characters of all chapters have been narrated.

    Returns:
        The paths of the written files, in the order of ``chapters``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    limiter = anyio.CapacityLimiter(concurrency)
    total = len(chapters)
    paths = [
        (output_dir / chapter_filename(chapter, total, engine.audio_suffix)).absolute()
        for chapter in chapters
    ]
    sizes = [len(chapter.content) for chapter in chapters]
    narrated = [0] * total
    progress(NarrationStarted(chapters=total, characters=sum(sizes)))

    def advance(index: int, characters: int) -> None:
        narrated[index] = min(characters, sizes[index])
        progress(Advanced(characters=sum(narrated)))

    async def process(index: int, chapter: BookContent, output_path: Path) -> None:
        async with limiter:
            position = index + 1
            progress(
                ChapterStarted(position=position, total=total, title=chapter.title)
            )
            await engine.synthesize(
                chapter.content, output_path, partial(advance, index)
            )
            advance(index, sizes[index])
            progress(
                ChapterNarrated(
                    position=position,
                    total=total,
                    title=chapter.title,
                    path=output_path,
                )
            )

    async with anyio.create_task_group() as task_group:
        for index, (chapter, output_path) in enumerate(
            zip(chapters, paths, strict=True)
        ):
            task_group.start_soon(process, index, chapter, output_path)

    return paths
