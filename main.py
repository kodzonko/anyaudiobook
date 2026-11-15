"""Entry point: convert an EPUB into a tagged MP3 audiobook.

Edit the settings below, then run ``uv run python main.py``.
"""

from pathlib import Path

from anyaudiobook import (
    DEFAULT_SKIP,
    EpubToAudiobookConverter,
    FilterOptions,
    tag_chapters,
)

EPUB_PATH = Path(r"C:\Users\username\path\to\ebook.epub")
OUTPUT_DIR = Path(r"C:\Users\username\path\to\output_dir")
VOICE = "pl-PL-ZofiaNeural"
PITCH = "-10Hz"
CONCURRENT_CHAPTERS = 5

AUTHOR = "Jane Doe"
BOOK_TITLE = "Lorem ipsum"
COVER_IMAGE: Path | None = Path(r"C:\Users\username\path\to\image.jpg")

# Front and back matter to leave out (see docs/filtering.md). For example,
# DEFAULT_SKIP - {MatterKind.DEDICATION} (MatterKind is in anyaudiobook) also
# narrates the dedication.
FILTER = FilterOptions(
    skip=DEFAULT_SKIP,
    include=(),  # regexes on file name or title to always narrate
    exclude=(),  # regexes on file name or title to never narrate
)
DRY_RUN = False  # True: only print what would be narrated and skipped


def main() -> None:
    """Convert the configured EPUB to MP3 chapters, then tag them."""
    converter = EpubToAudiobookConverter(EPUB_PATH, OUTPUT_DIR, VOICE, PITCH, FILTER)
    converter.chunk_epub()
    print(converter.report())
    if DRY_RUN:
        return
    converter.generate_audiobook(CONCURRENT_CHAPTERS)
    tag_chapters(OUTPUT_DIR, AUTHOR, BOOK_TITLE, COVER_IMAGE)


if __name__ == "__main__":
    main()
