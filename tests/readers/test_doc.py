"""Tests for DOC/RTF/ODT files, converted by real or stand-in programs."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from anyaudiobook import MissingToolError, read_book
from anyaudiobook.readers import DocReader
from tests.builders import Para, write_docx

LONG = " ".join(["The story goes on."] * 60)

_FAKE_SOFFICE = """#!/bin/sh
# Stand-in for LibreOffice: "converts" by copying a prepared DOCX.
echo "$@" > "$FAKE_SOFFICE_LOG"
while [ $# -gt 0 ]; do
  case "$1" in
    --outdir) shift; outdir="$1" ;;
    *) source="$1" ;;
  esac
  shift
done
name=$(basename "$source")
cp "$FAKE_SOFFICE_DOCX" "$outdir/${name%.*}.docx"
"""


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("textutil") is None,
    reason="needs macOS textutil",
)
def test_read_book_converts_doc_with_textutil(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = tmp_path / "source.html"
    html.write_text(
        '<html><head><meta charset="utf-8"><meta name="author" content="Jane Doe">'
        f"</head><body><h1>Chapter 1</h1><p>{LONG}</p>"
        f"<h1>Chapter 2</h1><p>{LONG}</p></body></html>",
        encoding="utf-8",
    )
    doc = tmp_path / "book.doc"
    subprocess.run(
        ["textutil", "-convert", "doc", "-output", str(doc), str(html)], check=True
    )
    monkeypatch.setenv("PATH", "/usr/bin")  # textutil, but no LibreOffice

    book = read_book(doc)

    assert [c.title for c in book.chapters] == ["Chapter 1", "Chapter 2"]
    assert book.metadata.authors == ("Jane Doe",)


def test_read_book_converts_doc_with_libreoffice_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    soffice = bin_dir / "soffice"
    soffice.write_text(_FAKE_SOFFICE)
    soffice.chmod(0o755)
    log = tmp_path / "soffice.log"
    docx = write_docx(
        tmp_path / "prepared.docx",
        [Para("Chapter 1", "Heading1"), Para(LONG)],
        title="Converted",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:/bin:/usr/bin")
    monkeypatch.setenv("FAKE_SOFFICE_DOCX", str(docx))
    monkeypatch.setenv("FAKE_SOFFICE_LOG", str(log))
    source = tmp_path / "book.rtf"
    source.write_text("{\\rtf1 placeholder}")

    book = read_book(source)

    assert book.metadata.title == "Converted"
    assert [c.title for c in book.chapters] == ["Chapter 1"]
    assert "--headless --convert-to docx" in log.read_text()


@pytest.mark.usefixtures("no_tools")
def test_doc_reader_explains_missing_converter(tmp_path: Path) -> None:
    source = tmp_path / "book.doc"
    source.write_bytes(b"\xd0\xcf\x11\xe0")

    with pytest.raises(MissingToolError, match="LibreOffice"):
        DocReader().read(source)
