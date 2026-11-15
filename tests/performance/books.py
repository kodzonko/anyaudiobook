"""Books of a chosen size, written in every input format, and silent narration.

The text is pseudo-random English-like prose, seeded by the book's name so
every run reads the same book, between front and back matter (copyright,
acknowledgments), so readers and the front and back matter classifier do the
work a real book needs. Formats that need an external program to be written
(DOC, MOBI, AZW3) skip the test when it is missing.
"""

import random
import shutil
import subprocess
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from html import escape
from pathlib import Path
from typing import ClassVar

import pytest
from ebooklib import epub

from anyaudiobook.models import BookContent, BookMetadata, CoverImage
from anyaudiobook.tts import TextProgress
from tests.builders import Para, PdfChapter, write_docx, write_pdf

TITLE = "Benchmark Book"
AUTHOR = "Jane Doe"
COPYRIGHT = (
    "Copyright © 2020 Jane Doe. All rights reserved. "
    "ISBN 978-0-00-000000-0. Published by Test Press."
)
THANKS = "Thanks to everyone who read the early drafts of this book."

_WORDS = [
    "the",
    "of",
    "and",
    "to",
    "in",
    "a",
    "was",
    "he",
    "that",
    "it",
    "his",
    "her",
    "with",
    "as",
    "had",
    "for",
    "she",
    "on",
    "at",
    "by",
    "not",
    "but",
    "be",
    "from",
    "they",
    "which",
    "you",
    "were",
    "all",
    "this",
    "one",
    "have",
    "so",
    "an",
    "him",
    "are",
    "said",
    "there",
    "their",
    "or",
    "them",
    "we",
    "been",
    "would",
    "what",
    "into",
    "could",
    "when",
    "if",
    "more",
    "no",
    "out",
    "up",
    "then",
    "little",
    "some",
    "time",
    "like",
    "only",
    "my",
    "about",
    "very",
    "man",
    "over",
    "before",
    "down",
    "must",
    "did",
    "see",
    "other",
    "upon",
    "these",
    "much",
    "way",
    "any",
    "well",
    "again",
    "come",
    "long",
    "day",
    "know",
    "old",
    "first",
    "never",
    "through",
    "house",
    "after",
    "made",
    "good",
    "own",
    "night",
    "away",
    "eyes",
    "great",
    "might",
    "hand",
    "life",
    "thought",
    "face",
    "still",
    "young",
    "those",
    "under",
    "door",
    "last",
    "morning",
    "light",
    "voice",
    "moment",
    "heart",
    "father",
    "mother",
    "water",
    "things",
    "river",
    "window",
    "across",
    "behind",
    "almost",
    "already",
    "garden",
    "letter",
    "silence",
    "winter",
    "summer",
    "evening",
    "table",
    "question",
    "harbour",
    "village",
    "answer",
    "whisper",
    "stranger",
    "mountain",
    "journey",
    "shadow",
    "promise",
    "remember",
    "quietly",
    "suddenly",
    "slowly",
    "together",
    "nothing",
    "everything",
    "somewhere",
]


@dataclass(frozen=True)
class BookSpec:
    """The size of a generated book: how many chapters of how many words."""

    name: str
    chapters: int
    words_per_chapter: int

    @property
    def words(self) -> int:
        """Words in all chapters together, front and back matter aside."""
        return self.chapters * self.words_per_chapter

    @property
    def chapter_titles(self) -> list[str]:
        """The titles of the chapters a reader should find, in order."""
        return [f"Chapter {number}" for number in range(1, self.chapters + 1)]


SHORT = BookSpec("short", chapters=5, words_per_chapter=2_000)
"""A novella: 10,000 words, about an hour of narration."""
NOVEL = BookSpec("novel", chapters=40, words_per_chapter=2_500)
"""A novel: 100,000 words, about eleven hours of narration."""
SIZES = (SHORT, NOVEL)


@dataclass(frozen=True)
class Part:
    """A titled part of a generated book: a chapter, or front or back matter."""

    title: str
    paragraphs: tuple[str, ...]


@cache
def parts(spec: BookSpec) -> tuple[Part, ...]:
    """Return the book's parts: copyright, the chapters, acknowledgments."""
    rng = random.Random(spec.name)
    chapters = tuple(
        Part(title, _paragraphs(rng, spec.words_per_chapter))
        for title in spec.chapter_titles
    )
    return (
        Part("Copyright", (COPYRIGHT,)),
        *chapters,
        Part("Acknowledgments", (THANKS,)),
    )


@cache
def chapters(spec: BookSpec) -> tuple[BookContent, ...]:
    """Return the book's chapters as the converter hands them to a writer."""
    return tuple(
        BookContent(
            chapter_number=number,
            title=part.title,
            content="\n".join((part.title, *part.paragraphs)),
        )
        for number, part in enumerate(parts(spec)[1:-1], start=1)
    )


def _paragraphs(rng: random.Random, words: int) -> tuple[str, ...]:
    """Return paragraphs of 3 to 7 sentences, about ``words`` words in all."""
    paragraphs: list[str] = []
    written = 0
    while written < words:
        sentences = []
        for _ in range(rng.randint(3, 7)):
            sentence = rng.choices(_WORDS, k=rng.randint(6, 18))
            written += len(sentence)
            if len(sentence) > 10:
                sentence[len(sentence) // 2] += ","
            sentences.append(" ".join(sentence).capitalize() + ".")
        paragraphs.append(" ".join(sentences))
    return tuple(paragraphs)


# --- Input formats -------------------------------------------------------------


def _write_txt(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """Plain text wrapped at 72 columns, as Project Gutenberg books are."""
    blocks = [
        block
        for part in parts(spec)
        for block in (part.title, *(textwrap.fill(p, 72) for p in part.paragraphs))
    ]
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _write_html(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """One HTML document with an ``<h1>`` per part."""
    body = "".join(
        f"<h1>{escape(part.title)}</h1>"
        + "".join(f"<p>{escape(p)}</p>" for p in part.paragraphs)
        for part in parts(spec)
    )
    path.write_text(
        f'<html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>'
        f'<meta name="author" content="{AUTHOR}"></head><body>{body}</body></html>',
        encoding="utf-8",
    )


def _write_epub(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """An EPUB with one XHTML document and table of contents entry per part."""
    book = epub.EpubBook()
    book.set_identifier(f"benchmark-{spec.name}")
    book.set_title(TITLE)
    book.set_language("en")
    book.add_author(AUTHOR)
    items = []
    for number, part in enumerate(parts(spec)):
        item = epub.EpubHtml(
            title=part.title, file_name=f"part-{number:03}.xhtml", lang="en"
        )
        paragraphs = "".join(f"<p>{escape(p)}</p>" for p in part.paragraphs)
        item.content = (
            f"<html><body><h1>{escape(part.title)}</h1>{paragraphs}</body></html>"
        )
        book.add_item(item)
        items.append(item)
    book.toc = [
        epub.Link(item.file_name, part.title, f"toc-{number}")
        for number, (item, part) in enumerate(zip(items, parts(spec), strict=True))
    ]
    book.spine = items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


def _write_docx(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """A DOCX with a ``Heading 1`` paragraph per part."""
    write_docx(
        path,
        [
            para
            for part in parts(spec)
            for para in (Para(part.title, "Heading1"), *map(Para, part.paragraphs))
        ],
        title=TITLE,
        author=AUTHOR,
    )


def _write_pdf(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """An A5 PDF with running headers, page numbers and an outline entry per part."""
    write_pdf(
        path,
        [PdfChapter(part.title, part.paragraphs) for part in parts(spec)],
        title=TITLE,
        author=AUTHOR,
        running_header=TITLE,
    )


def _write_doc(shelf: Shelf, spec: BookSpec, path: Path) -> None:
    """A Word 97 DOC converted by LibreOffice, else by macOS ``textutil``."""
    if soffice := shutil.which("soffice"):
        docx = shelf.book(spec, ".docx")
        _run(
            soffice, "--headless", "--convert-to", "doc", "--outdir", path.parent, docx
        )
    elif textutil := shutil.which("textutil"):
        html = shelf.book(spec, ".html")
        _run(textutil, "-convert", "doc", "-output", path, html)
    else:
        pytest.skip("writing a DOC needs LibreOffice or macOS textutil")


def _kindle(*options: str) -> Callable[[Shelf, BookSpec, Path], None]:
    """Return a writer converting the EPUB to a Kindle book with Calibre."""

    def write(shelf: Shelf, spec: BookSpec, path: Path) -> None:
        ebook_convert = shutil.which("ebook-convert")
        if ebook_convert is None:
            pytest.skip("writing a Kindle book needs Calibre's ebook-convert")
        _run(ebook_convert, shelf.book(spec, ".epub"), path, *options)

    return write


def _run(*command: str | Path) -> None:
    """Run a program converting a book, failing loudly if it fails."""
    subprocess.run([str(part) for part in command], check=True, capture_output=True)


_WRITERS: dict[str, Callable[[Shelf, BookSpec, Path], None]] = {
    ".epub": _write_epub,
    ".pdf": _write_pdf,
    ".docx": _write_docx,
    ".doc": _write_doc,
    ".mobi": _kindle("--mobi-file-type", "old"),
    ".azw3": _kindle(),
    ".txt": _write_txt,
    ".html": _write_html,
}
INPUT_FORMATS = tuple(_WRITERS)
"""Extensions of the input formats benchmarked, one per reader code path."""


class Shelf:
    """Generated books in a directory, each written on first request only.

    Writing the novel as a PDF or Kindle book takes seconds, so one shelf
    serves the whole test session.
    """

    def __init__(self, directory: Path) -> None:
        """Keep the books in ``directory``."""
        self.directory = directory

    def book(self, spec: BookSpec, extension: str) -> Path:
        """Return the book of size ``spec`` in the format of ``extension``.

        Skips the test if the format needs a program that is not installed.
        """
        path = self.directory / spec.name / f"book{extension}"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            _WRITERS[extension](self, spec, path)
        return path


# --- Narration -----------------------------------------------------------------

# MPEG-2 Layer III, 48 kbit/s, 24 kHz, mono, no CRC: Edge TTS's default format.
_FRAME_HEADER = bytes([0xFF, 0xF3, 0x64, 0xC0])
_FRAME_BYTES = 144
_FRAME_SECONDS = 576 / 24_000


def edge_like_silence(seconds: float) -> bytes:
    """Return silence lasting about ``seconds`` in the MP3 format of Edge TTS."""
    frame = _FRAME_HEADER + bytes(_FRAME_BYTES - len(_FRAME_HEADER))
    return frame * max(1, round(seconds / _FRAME_SECONDS))


@dataclass(frozen=True)
class SilentSpeech:
    """A speech engine writing silence as long as narrating the text would take.

    The files have Edge TTS's sample rate and bitrate and last as long as
    reading the text aloud at about 150 words a minute, so writers package
    as much audio as after a real narration, without the network.
    """

    audio_suffix: ClassVar[str] = ".mp3"
    characters_per_second: ClassVar[float] = 15.0

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Write silence for ``text`` to ``output_path``."""
        output_path.write_bytes(
            edge_like_silence(len(text) / self.characters_per_second)
        )


def narration_seconds(spec: BookSpec) -> float:
    """Return how long the narration of a book's chapters lasts."""
    characters = sum(len(chapter.content) for chapter in chapters(spec))
    return characters / SilentSpeech.characters_per_second


def benchmark_metadata() -> BookMetadata:
    """Return tags with a 300 kB cover, the size of a typical ebook cover.

    Writers embed the cover in every MP3 file, so its size matters.
    """
    cover = b"\xff\xd8\xff\xe0" + random.Random("cover").randbytes(300_000)
    return BookMetadata(
        title=TITLE, authors=(AUTHOR,), cover=CoverImage(cover, "image/jpeg")
    )
