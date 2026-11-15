"""Tests for single-file HTML books, read from real files."""

from pathlib import Path

from anyaudiobook import MatterKind, read_book, read_source

LONG = " ".join(["word"] * 200)


def test_read_book_reads_html_head_and_splits_at_headings(tmp_path: Path) -> None:
    path = tmp_path / "book.html"
    path.write_text(
        '<html lang="pl"><head><title>Tytuł</title>'
        '<meta name="Author" content="Jan Kowalski"><meta name="author" content="Jan Kowalski">'
        "<style>h1 {color: red}</style></head><body>"
        '<div class="toc"><p><a href="#c1">Chapter 1</a></p><p><a href="#c2">Chapter 2</a></p>'
        '<p><a href="#n">Notes</a></p></div>'
        f'<h1 id="c1">Chapter 1</h1><p>{LONG}<sup><a href="#n1">1</a></sup></p>'
        f'<h1 id="c2">Chapter 2</h1><p>{LONG}</p>'
        '<h1 id="n">Notes</h1><p id="n1"><a href="#c1">1</a> A note.</p>'
        "</body></html>",
        encoding="utf-8",
    )

    book = read_book(path)

    assert (book.metadata.title, book.metadata.authors, book.metadata.language) == (
        "Tytuł",
        ("Jan Kowalski",),
        "pl",
    )
    assert [d.kind for d in book.decisions] == [
        MatterKind.TOC,
        MatterKind.BODY,
        MatterKind.BODY,
        MatterKind.NOTES,
    ]
    assert book.chapters[0].content == f"Chapter 1\n{LONG}"


def test_read_source_finds_headings_by_css_font_size(tmp_path: Path) -> None:
    # The shape of HTML that macOS textutil writes for Word documents.
    path = tmp_path / "converted.htm"
    path.write_text(
        "<html><head><style>p.p1 {font: 24.0px Times} p.p2 {font: 12.0px Times}"
        "</style></head><body>"
        f"<p class='p1'><b>The Beginning</b></p><p class='p2'>{LONG}</p>"
        f"<p class='p1'><b>The End</b></p><p class='p2'>{LONG}</p>"
        "</body></html>",
        encoding="utf-8",
    )

    documents = read_source(path).documents

    assert [d.toc_label for d in documents] == ["The Beginning", "The End"]
