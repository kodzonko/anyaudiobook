"""Convert EPUB ebooks into MP3 audiobooks with Edge TTS."""

from anyaudiobook.converter import EpubToAudiobookConverter
from anyaudiobook.epub_parser import ParsedBook, read_book, read_chapters
from anyaudiobook.matter import DEFAULT_SKIP, Decision, FilterOptions, MatterKind
from anyaudiobook.metadata import add_metadata, tag_chapters
from anyaudiobook.models import BookContent
from anyaudiobook.report import format_report
from anyaudiobook.tts import get_available_voices, synthesize_chapters

__all__ = [
    "DEFAULT_SKIP",
    "BookContent",
    "Decision",
    "EpubToAudiobookConverter",
    "FilterOptions",
    "MatterKind",
    "ParsedBook",
    "add_metadata",
    "format_report",
    "get_available_voices",
    "read_book",
    "read_chapters",
    "synthesize_chapters",
    "tag_chapters",
]
