"""Convert ebooks (EPUB, PDF, DOCX, DOC, MOBI, AZW3, TXT, HTML) into
audiobooks (MP3 chapters or M4B) with Edge TTS."""

from anyaudiobook.converter import AudiobookConverter
from anyaudiobook.errors import (
    AnyAudiobookError,
    MissingToolError,
    UnreadableBookError,
    UnsupportedFormatError,
)
from anyaudiobook.matter import DEFAULT_SKIP, Decision, FilterOptions, MatterKind
from anyaudiobook.metadata import add_metadata, tag_chapters
from anyaudiobook.models import (
    BookContent,
    BookMetadata,
    CoverImage,
    Document,
    SourceBook,
)
from anyaudiobook.readers import (
    READERS,
    BookReader,
    HtmlBookReader,
    read_source,
    reader_for,
)
from anyaudiobook.report import format_report
from anyaudiobook.selection import ParsedBook, read_book, read_chapters, select_chapters
from anyaudiobook.tts import (
    EdgeTTS,
    SpeechEngine,
    get_available_voices,
    synthesize_chapters,
)
from anyaudiobook.writers import (
    WRITERS,
    AudiobookWriter,
    M4bWriter,
    Mp3Writer,
    writer_for,
)

__all__ = [
    "DEFAULT_SKIP",
    "READERS",
    "WRITERS",
    "AnyAudiobookError",
    "AudiobookConverter",
    "AudiobookWriter",
    "BookContent",
    "BookMetadata",
    "BookReader",
    "CoverImage",
    "Decision",
    "Document",
    "EdgeTTS",
    "FilterOptions",
    "HtmlBookReader",
    "M4bWriter",
    "MatterKind",
    "MissingToolError",
    "Mp3Writer",
    "ParsedBook",
    "SourceBook",
    "SpeechEngine",
    "UnreadableBookError",
    "UnsupportedFormatError",
    "add_metadata",
    "format_report",
    "get_available_voices",
    "read_book",
    "read_chapters",
    "read_source",
    "reader_for",
    "select_chapters",
    "synthesize_chapters",
    "tag_chapters",
    "writer_for",
]
