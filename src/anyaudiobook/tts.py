"""Turn chapter text into speech with Edge TTS."""

from collections.abc import Sequence
from pathlib import Path

import anyio
import edge_tts
from edge_tts.typing import Voice

from anyaudiobook.filenames import chapter_filename
from anyaudiobook.models import BookContent

_RED = "\033[31m"
_GREY = "\033[90m"
_RESET = "\033[0m"


async def get_available_voices() -> list[Voice]:
    """Return the voices the Edge TTS service offers."""
    return await edge_tts.list_voices()


async def synthesize_chapter(
    chapter: BookContent, output_path: Path, voice: str, pitch: str = "+0Hz"
) -> None:
    """Narrate one chapter and save it as an MP3 file.

    Args:
        chapter: The chapter to narrate.
        output_path: Where to write the MP3 file.
        voice: Edge TTS voice short name, e.g. ``en-US-BrianNeural``.
        pitch: Pitch adjustment, e.g. ``-10Hz``.
    """
    communicate = edge_tts.Communicate(chapter.content, voice, pitch=pitch)
    await communicate.save(str(output_path))


async def synthesize_chapters(
    chapters: Sequence[BookContent],
    output_dir: Path,
    voice: str,
    pitch: str = "+0Hz",
    concurrency: int = 10,
) -> list[Path]:
    """Narrate chapters concurrently, writing one MP3 file per chapter.

    Args:
        chapters: The chapters to narrate.
        output_dir: Directory for the MP3 files; created if missing.
        voice: Edge TTS voice short name.
        pitch: Pitch adjustment.
        concurrency: Most chapters narrated at the same time.

    Returns:
        The paths of the written files, in the order of ``chapters``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    limiter = anyio.CapacityLimiter(concurrency)
    total = len(chapters)
    paths = [
        (output_dir / chapter_filename(chapter, total)).absolute()
        for chapter in chapters
    ]

    async def process(chapter: BookContent, output_path: Path) -> None:
        async with limiter:
            print(
                f"Processing chapter: {chapter.chapter_number}/{total} {_RED}{chapter.title}{_RESET}"
            )
            await synthesize_chapter(chapter, output_path, voice, pitch)
            print(
                f"Saved: {chapter.chapter_number}/{total} {_RED}{chapter.title}{_RESET}"
                f" in {_GREY}{output_path}{_RESET}"
            )

    async with anyio.create_task_group() as task_group:
        for chapter, output_path in zip(chapters, paths, strict=True):
            task_group.start_soon(process, chapter, output_path)

    return paths
