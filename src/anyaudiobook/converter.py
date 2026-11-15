"""High-level EPUB to audiobook conversion."""

from pathlib import Path

import anyio

from anyaudiobook.epub_parser import read_chapters
from anyaudiobook.models import BookContent
from anyaudiobook.tts import synthesize_chapters


class EpubToAudiobookConverter:
    """Convert an EPUB file into one MP3 file per chapter."""

    def __init__(
        self,
        epub_path: str | Path,
        output_dir: str | Path,
        voice: str,
        pitch: str = "+0Hz",
    ) -> None:
        """Set up a conversion.

        Args:
            epub_path: Path to the EPUB file.
            output_dir: Directory for the MP3 files.
            voice: Edge TTS voice short name, e.g. ``en-US-BrianNeural``.
            pitch: Pitch adjustment, e.g. ``-10Hz``.
        """
        self.epub_path = Path(epub_path)
        self.audiobook_path = Path(output_dir)
        self.voice = voice
        self.pitch = pitch
        self.chunked_content: list[BookContent] = []

    def chunk_epub(self) -> None:
        """Split the EPUB into chapters, stored in ``chunked_content``."""
        self.chunked_content = read_chapters(self.epub_path)

    def generate_audiobook(self, number_of_concurrent_tasks: int = 10) -> list[Path]:
        """Narrate the chunked chapters into MP3 files.

        Args:
            number_of_concurrent_tasks: Most chapters narrated at the same time.

        Returns:
            The paths of the written files.
        """
        return anyio.run(
            synthesize_chapters,
            self.chunked_content,
            self.audiobook_path,
            self.voice,
            self.pitch,
            number_of_concurrent_tasks,
        )
