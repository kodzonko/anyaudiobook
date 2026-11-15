"""End-to-end tests: real ebooks of every format to real audio files.

Only the speech engine is replaced, by one writing silent MP3s.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4

from anyaudiobook import (
    DEFAULT_SKIP,
    AudiobookConverter,
    BookMetadata,
    CoverImage,
    FilterOptions,
    M4bWriter,
    MatterKind,
    UnsupportedFormatError,
)
from tests.builders import FakeEngine, Para, PdfChapter, write_docx, write_pdf
from tests.conftest import FIXTURES

LONG = " ".join(["The story goes on."] * 60)

BookFactory = Callable[[Path], Path]


def _txt(directory: Path) -> Path:
    path = directory / "Plain Book.txt"
    path.write_text(
        "Copyright © 2020 Jane Doe. All rights reserved. ISBN 978-0-00-000000-0\n\n"
        f"Chapter 1\n\n{LONG}\n\nChapter 2\n\n{LONG}\n\nAcknowledgments\n\nThanks.\n",
        encoding="utf-8",
    )
    return path


def _docx(directory: Path) -> Path:
    return write_docx(
        directory / "book.docx",
        [
            Para("Copyright © 2020 Jane Doe. All rights reserved."),
            Para("Chapter 1", "Heading1"),
            Para(LONG, footnote="A note."),
            Para("Chapter 2", "Heading1"),
            Para(LONG),
            Para("Acknowledgments", "Heading1"),
            Para("Thanks."),
        ],
    )


def _pdf(directory: Path) -> Path:
    return write_pdf(
        directory / "book.pdf",
        [
            PdfChapter(
                "Copyright", ["Copyright © 2020 Jane Doe. All rights reserved."]
            ),
            PdfChapter("Chapter 1", [LONG]),
            PdfChapter("Chapter 2", [LONG]),
            PdfChapter("Acknowledgments", ["Thanks."]),
        ],
    )


def _html(directory: Path) -> Path:
    path = directory / "book.html"
    path.write_text(
        "<html><head><title>HTML Book</title></head><body>"
        "<p>Copyright © 2020 Jane Doe. All rights reserved. ISBN 978-0-00-000000-0</p>"
        f"<h1>Chapter 1</h1><p>{LONG}</p><h1>Chapter 2</h1><p>{LONG}</p>"
        "<h1>Acknowledgments</h1><p>Thanks.</p></body></html>",
        encoding="utf-8",
    )
    return path


def _fixture(name: str) -> BookFactory:
    def copy(directory: Path) -> Path:
        return Path(shutil.copy(FIXTURES / name, directory / name))

    return copy


@pytest.mark.parametrize(
    ("make_book", "titles"),
    [
        (_txt, ["Chapter 1", "Chapter 2"]),
        (_docx, ["Chapter 1", "Chapter 2"]),
        (_pdf, ["Chapter 1", "Chapter 2"]),
        (_html, ["Chapter 1", "Chapter 2"]),
        (_fixture("book.mobi"), ["Chapter 1. Beginnings", "Chapter 2. Endings"]),
        (_fixture("book.azw3"), ["Chapter 1. Beginnings", "Chapter 2. Endings"]),
    ],
    ids=["txt", "docx", "pdf", "html", "mobi", "azw3"],
)
def test_converter_turns_every_format_into_tagged_mp3_chapters(
    tmp_path: Path, fake_engine: FakeEngine, make_book: BookFactory, titles: list[str]
) -> None:
    output = tmp_path / "audiobook"
    converter = AudiobookConverter(make_book(tmp_path), output, fake_engine)

    paths = converter.convert(concurrency=2)

    assert [p.name for p in paths] == [f"{n}. {t}.mp3" for n, t in enumerate(titles, 1)]
    assert [t.splitlines()[0] for t in fake_engine.texts] == titles
    assert not any(
        "Thanks" in text or "rights reserved" in text for text in fake_engine.texts
    )
    assert EasyID3(str(paths[0]))["album"] == [converter.metadata.title]


def test_converter_turns_epub_into_chapter_files(
    epub_file: Path, tmp_path: Path, fake_engine: FakeEngine
) -> None:
    output_dir = tmp_path / "audiobook"
    converter = AudiobookConverter(epub_file, output_dir, fake_engine)

    paths = converter.convert(concurrency=2)

    assert [c.title for c in converter.chapters] == ["Beginning", "The End"]
    assert sorted(p.name for p in output_dir.iterdir()) == [
        "1. Beginning.mp3",
        "2. The End.mp3",
    ]
    assert fake_engine.texts[0].endswith("First words.")
    assert EasyID3(str(paths[0]))["album"] == ["Test Book"]


@pytest.mark.usefixtures("ffmpeg")
def test_converter_writes_m4b_from_docx(
    tmp_path: Path, fake_engine: FakeEngine
) -> None:
    converter = AudiobookConverter(
        _docx(tmp_path), tmp_path / "out", fake_engine, output_format="m4b"
    )

    (path,) = converter.convert()

    assert path == tmp_path / "out" / "Test Document.m4b"
    assert MP4(path).chapters is not None
    assert [chapter.title for chapter in MP4(path).chapters] == [  # ty: ignore[not-iterable]
        "Chapter 1",
        "Chapter 2",
    ]


def test_converter_reports_and_filters_with_options(epub_file: Path) -> None:
    options = FilterOptions(skip=DEFAULT_SKIP - {MatterKind.ACKNOWLEDGMENTS})
    converter = AudiobookConverter(
        epub_file, "unused", FakeEngine(), filter_options=options
    )

    report = converter.report()

    assert [c.title for c in converter.chapters] == [
        "Beginning",
        "Podziękowania",
        "The End",
    ]
    assert len(converter.decisions) == 4
    assert "acknowledgments" in report
    assert report.endswith("Narrating 3 of 4 documents (11 words), skipping 1.")


def test_converter_rereads_after_options_change(epub_file: Path) -> None:
    converter = AudiobookConverter(epub_file, "unused", FakeEngine())
    assert len(converter.chapters) == 2

    converter.filter_options = FilterOptions(exclude=("end",))
    converter.read()

    assert [c.title for c in converter.chapters] == ["Beginning"]


def test_converter_metadata_prefers_overrides_then_book_then_file_name(
    tmp_path: Path,
) -> None:
    cover_file = tmp_path / "cover.png"
    cover_file.write_bytes(b"png")
    book = _txt(tmp_path)

    plain = AudiobookConverter(book, "unused", FakeEngine()).metadata
    custom = AudiobookConverter(
        book,
        "unused",
        FakeEngine(),
        metadata=BookMetadata(authors=("Ann",), cover=CoverImage.from_file(cover_file)),
    ).metadata

    assert (plain.title, plain.authors, plain.cover) == ("Plain Book", (), None)
    assert (custom.title, custom.authors) == ("Plain Book", ("Ann",))
    assert custom.cover == CoverImage(b"png", "image/png")


def test_converter_accepts_configured_writer_and_rejects_unknown_formats(
    epub_file: Path,
) -> None:
    writer = M4bWriter(bitrate="96k")

    assert (
        AudiobookConverter(epub_file, "x", FakeEngine(), output_format=writer).writer
        is writer
    )
    with pytest.raises(UnsupportedFormatError, match="ogg"):
        AudiobookConverter(epub_file, "x", FakeEngine(), output_format="ogg")
