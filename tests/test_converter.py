"""End-to-end tests for the converter, with only Edge TTS mocked out."""

from pathlib import Path
from unittest.mock import patch

from anyaudiobook import EpubToAudiobookConverter, tts


class SilentCommunicate:
    """Stand-in for ``edge_tts.Communicate`` that writes the text it was given."""

    def __init__(self, text: str, voice: str, pitch: str) -> None:
        """Keep the text to write on save."""
        self.text = text

    async def save(self, path: str) -> None:
        """Write the chapter text instead of audio."""
        Path(path).write_text(self.text)


def test_converter_turns_epub_into_chapter_files(
    epub_file: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "audiobook"
    converter = EpubToAudiobookConverter(epub_file, output_dir, "en-US-BrianNeural")

    converter.chunk_epub()
    with patch.object(tts.edge_tts, "Communicate", SilentCommunicate):
        paths = converter.generate_audiobook(number_of_concurrent_tasks=2)

    assert [c.title for c in converter.chunked_content] == ["Beginning", "The End"]
    assert sorted(p.name for p in output_dir.iterdir()) == [
        "1. Beginning.mp3",
        "2. The End.mp3",
    ]
    assert paths[0].read_text().endswith("First words.")
