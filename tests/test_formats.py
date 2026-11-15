"""Tests for picking a reader or writer by file extension or format name."""

from pathlib import Path

import pytest

from anyaudiobook.errors import UnsupportedFormatError
from anyaudiobook.readers import READERS, read_source, reader_for
from anyaudiobook.readers.doc import DocReader
from anyaudiobook.readers.docx import DocxReader
from anyaudiobook.readers.epub import EpubReader
from anyaudiobook.readers.html import HtmlReader
from anyaudiobook.readers.mobi import MobiReader
from anyaudiobook.readers.pdf import PdfReader
from anyaudiobook.readers.txt import TextReader
from anyaudiobook.writers import WRITERS, writer_for
from anyaudiobook.writers.m4b import M4bWriter
from anyaudiobook.writers.mp3 import Mp3Writer


@pytest.mark.parametrize(
    ("name", "reader"),
    [
        ("book.epub", EpubReader),
        ("book.PDF", PdfReader),
        ("book.docx", DocxReader),
        ("book.doc", DocReader),
        ("book.rtf", DocReader),
        ("book.odt", DocReader),
        ("book.mobi", MobiReader),
        ("book.azw", MobiReader),
        ("book.azw3", MobiReader),
        ("book.txt", TextReader),
        ("book.html", HtmlReader),
        ("book.xhtml", HtmlReader),
    ],
)
def test_reader_for_picks_reader_by_extension(name: str, reader: type) -> None:
    assert isinstance(reader_for(name), reader)


def test_reader_for_rejects_unknown_extensions_listing_known_ones() -> None:
    with pytest.raises(UnsupportedFormatError, match=r"'\.cbz'.*\.epub"):
        reader_for("comic.cbz")


def test_read_source_reports_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing.epub"):
        read_source(tmp_path / "missing.epub")


@pytest.mark.parametrize(
    ("name", "writer"), [("mp3", Mp3Writer), ("M4B", M4bWriter), (".m4b", M4bWriter)]
)
def test_writer_for_picks_writer_by_name(name: str, writer: type) -> None:
    assert isinstance(writer_for(name), writer)


def test_supported_formats_are_listed() -> None:
    assert {".epub", ".pdf", ".docx", ".mobi", ".azw3", ".txt"} <= READERS.keys()
    assert sorted(WRITERS) == ["m4b", "mp3"]
