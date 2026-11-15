"""Convert EPUB ebooks into MP3 audiobooks with Edge TTS."""

from anyaudiobook.converter import EpubToAudiobookConverter
from anyaudiobook.epub_parser import read_chapters
from anyaudiobook.metadata import add_metadata, tag_chapters
from anyaudiobook.models import BookContent
from anyaudiobook.tts import get_available_voices, synthesize_chapters

__all__ = [
    "BookContent",
    "EpubToAudiobookConverter",
    "add_metadata",
    "get_available_voices",
    "read_chapters",
    "synthesize_chapters",
    "tag_chapters",
]
