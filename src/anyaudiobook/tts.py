"""Turn chapter text into speech.

Speech engines are interchangeable: anything with an ``audio_suffix`` and an
async ``synthesize(text, path)`` method is a :class:`SpeechEngine`.
:class:`EdgeTTS`, Microsoft Edge's online voices, is the one built in.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol

import anyio
import edge_tts
from edge_tts.typing import Voice

from anyaudiobook.filenames import chapter_filename
from anyaudiobook.models import BookContent

_RED = "\033[31m"
_GREY = "\033[90m"
_RESET = "\033[0m"


class SpeechEngine(Protocol):
    """Narrates text into an audio file."""

    @property
    def audio_suffix(self) -> str:
        """Extension of the files :meth:`synthesize` writes, e.g. ``.mp3``."""
        ...

    async def synthesize(self, text: str, output_path: Path) -> None:
        """Narrate ``text`` and save the audio to ``output_path``."""
        ...


@dataclass(frozen=True, slots=True)
class EdgeTTS:
    """Microsoft Edge's online text-to-speech voices; writes MP3 files.

    Args:
        voice: Voice short name, e.g. ``en-US-BrianNeural``; see
            :func:`get_available_voices`.
        pitch: Pitch adjustment, e.g. ``-10Hz``.
        rate: Speed adjustment, e.g. ``+10%``.
        volume: Volume adjustment, e.g. ``-20%``.
    """

    voice: str
    pitch: str = "+0Hz"
    rate: str = "+0%"
    volume: str = "+0%"
    audio_suffix: ClassVar[str] = ".mp3"

    async def synthesize(self, text: str, output_path: Path) -> None:
        """Narrate ``text`` into an MP3 file at ``output_path``."""
        communicate = edge_tts.Communicate(
            text, self.voice, pitch=self.pitch, rate=self.rate, volume=self.volume
        )
        await communicate.save(str(output_path))


async def get_available_voices() -> list[Voice]:
    """Return the voices the Edge TTS service offers."""
    return await edge_tts.list_voices()


async def synthesize_chapters(
    chapters: Sequence[BookContent],
    output_dir: Path,
    engine: SpeechEngine,
    concurrency: int = 10,
) -> list[Path]:
    """Narrate chapters concurrently, writing one audio file per chapter.

    Files are named ``NN. Title`` plus the engine's extension.

    Args:
        chapters: The chapters to narrate.
        output_dir: Directory for the audio files; created if missing.
        engine: The speech engine to narrate with.
        concurrency: Most chapters narrated at the same time.

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

    async def process(chapter: BookContent, output_path: Path) -> None:
        async with limiter:
            print(
                f"Processing chapter: {chapter.chapter_number}/{total} {_RED}{chapter.title}{_RESET}"
            )
            await engine.synthesize(chapter.content, output_path)
            print(
                f"Saved: {chapter.chapter_number}/{total} {_RED}{chapter.title}{_RESET}"
                f" in {_GREY}{output_path}{_RESET}"
            )

    async with anyio.create_task_group() as task_group:
        for chapter, output_path in zip(chapters, paths, strict=True):
            task_group.start_soon(process, chapter, output_path)

    return paths
