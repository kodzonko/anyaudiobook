"""Entry point: convert an EPUB into a tagged MP3 audiobook.

Edit the settings below, then run ``uv run python main.py``.
"""

from pathlib import Path

from anyaudiobook import EpubToAudiobookConverter, tag_chapters

EPUB_PATH = Path(r"C:\Users\username\path\to\ebook.epub")
OUTPUT_DIR = Path(r"C:\Users\username\path\to\output_dir")
VOICE = "pl-PL-ZofiaNeural"
PITCH = "-10Hz"
CONCURRENT_CHAPTERS = 5

AUTHOR = "Jane Doe"
BOOK_TITLE = "Lorem ipsum"
COVER_IMAGE: Path | None = Path(r"C:\Users\username\path\to\image.jpg")


def main() -> None:
    """Convert the configured EPUB to MP3 chapters, then tag them."""
    converter = EpubToAudiobookConverter(EPUB_PATH, OUTPUT_DIR, VOICE, PITCH)
    converter.chunk_epub()
    converter.generate_audiobook(CONCURRENT_CHAPTERS)
    tag_chapters(OUTPUT_DIR, AUTHOR, BOOK_TITLE, COVER_IMAGE)


if __name__ == "__main__":
    main()
