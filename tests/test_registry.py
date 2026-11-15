"""Tests for the format registries and format lookup."""

from pathlib import Path

import pytest

from anyaudiobook import (
    READERS,
    WRITERS,
    M4bWriter,
    Mp3Writer,
    UnsupportedFormatError,
    read_source,
    reader_for,
    writer_for,
)
from anyaudiobook.readers import (
    DocReader,
    DocxReader,
    EpubReader,
    HtmlReader,
    MobiReader,
    PdfReader,
    TextReader,
)
from anyaudiobook.registry import Registry


def test_registry_creates_by_name_ignoring_case() -> None:
    registry: Registry[list[int]] = Registry("thing")
    registry.register(list, "List", "seq")

    assert registry.create("LIST") == []
    assert "Seq" in registry
    assert 3 not in registry
    assert registry.names == ("list", "seq")


def test_registry_lets_later_registrations_win() -> None:
    registry: Registry[object] = Registry("thing")
    registry.register(int, "x")
    registry.register(str, "x")

    assert registry.create("x") == ""


def test_registry_rejects_unknown_names_listing_known_ones() -> None:
    registry: Registry[object] = Registry("colour")
    registry.register(object, "red", "blue")

    with pytest.raises(UnsupportedFormatError, match="colour 'green'.*blue, red"):
        registry.create("green")


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


def test_reader_for_rejects_unknown_extensions() -> None:
    with pytest.raises(UnsupportedFormatError, match=r"\.cbz"):
        reader_for("comic.cbz")


def test_read_source_reports_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing.epub"):
        read_source(tmp_path / "missing.epub")


@pytest.mark.parametrize(
    ("name", "writer"), [("mp3", Mp3Writer), ("M4B", M4bWriter), (".m4b", M4bWriter)]
)
def test_writer_for_picks_writer_by_name(name: str, writer: type) -> None:
    assert isinstance(writer_for(name), writer)


def test_registries_list_supported_formats() -> None:
    assert {".epub", ".pdf", ".docx", ".mobi", ".azw3", ".txt"} <= set(READERS.names)
    assert WRITERS.names == ("m4b", "mp3")
