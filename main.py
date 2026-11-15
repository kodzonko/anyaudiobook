"""Entry point: convert an ebook into a tagged audiobook.

Edit the settings below, then run ``uv run python main.py``.
"""

from pathlib import Path

from anyaudiobook import (
    DEFAULT_SKIP,
    AudiobookConverter,
    BookMetadata,
    EdgeTTS,
    FilterOptions,
)

# Any supported ebook: .epub, .pdf, .docx, .doc, .rtf, .odt, .mobi, .azw,
# .azw3, .txt, .html (see docs/formats.md).
SOURCE = Path(r"C:\Users\username\path\to\ebook.epub")
# "mp3": one file per chapter in the OUTPUT directory.
# "m4b": one audiobook file with chapter markers (needs ffmpeg); OUTPUT may be
# the .m4b file or a directory to put "<title>.m4b" in.
OUTPUT_FORMAT = "mp3"
OUTPUT = Path(r"C:\Users\username\path\to\output_dir")
VOICE = EdgeTTS("pl-PL-ZofiaNeural", pitch="-10Hz")
CONCURRENT_CHAPTERS = 5

# Title, authors and cover are read from the ebook; set any of them here to
# override it.
METADATA = BookMetadata(
    title=None,  # e.g. "Lorem ipsum"
    authors=(),  # e.g. ("Jane Doe",)
    cover=None,  # e.g. CoverImage.from_file(r"C:\path\to\cover.jpg")
)

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
    """Convert the configured ebook into an audiobook."""
    converter = AudiobookConverter(
        SOURCE,
        OUTPUT,
        VOICE,
        output_format=OUTPUT_FORMAT,
        filter_options=FILTER,
        metadata=METADATA,
    )
    print(converter.report())
    if DRY_RUN:
        return
    for path in converter.convert(CONCURRENT_CHAPTERS):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
