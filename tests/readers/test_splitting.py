"""Tests for cutting one long HTML document into the parts of a book."""

import pytest
from bs4 import BeautifulSoup, Tag

from anyaudiobook.markup import extract_text, parse_html
from anyaudiobook.readers.splitting import (
    TOC_LABEL,
    heading_split_level,
    mark_toc,
    relink,
    split_sections,
    toc_depth,
)


def _body(html: str) -> Tag:
    """Parse body HTML."""
    return parse_html(f"<html><body>{html}</body></html>")


def _split(html: str) -> list[tuple[str | None, str]]:
    """Split body HTML and return each section's label and text."""
    return [(s.label, extract_text(s.body)) for s in split_sections(_body(html))]


def test_split_sections_starts_a_section_at_each_heading() -> None:
    sections = _split("<p>Title page</p><h1>One</h1><p>a</p><h1>Two</h1><p>b</p>")

    assert sections == [(None, "Title page"), ("One", "One\na"), ("Two", "Two\nb")]


def test_split_sections_uses_second_level_when_first_holds_only_the_title() -> None:
    sections = _split(
        "<h1>Book</h1><p>by me</p><h2>One</h2><p>a</p><h2>Two</h2><h3>x</h3>"
    )

    assert [label for label, _ in sections] == ["Book", "One", "Two"]


def test_split_sections_opens_wrappers_holding_several_headings() -> None:
    sections = _split(
        "<div class='book'><section><h1>One</h1><p>a</p></section>"
        "<div><p>intro</p><h1>Two</h1><p>b</p></div></div>"
    )

    # Text before a heading belongs to the section before it.
    assert sections == [("One", "One\na\nintro"), ("Two", "Two\nb")]


def test_split_sections_keeps_wrappers_that_begin_with_their_heading() -> None:
    body = _body(
        "<h1>One</h1><p>a</p>"
        '<section epub:type="appendix"><h1>Two</h1><p>b</p></section>'
    )

    second = split_sections(body)[1].body

    assert second.find("section", attrs={"epub:type": "appendix"}) is not None


def test_split_sections_prefers_toc_entries_over_headings() -> None:
    sections = _split(
        f'<p {TOC_LABEL}="Chapter 1">Start</p><h1>Inner</h1><p>a</p>'
        f'<p {TOC_LABEL}=" Chapter\n2 ">Later</p>'
    )

    assert sections == [("Chapter 1", "Start\nInner\na"), ("Chapter 2", "Later")]


def test_split_sections_always_separates_note_collections() -> None:
    sections = _split(
        "<h1>One</h1><p>a</p>"
        '<ol role="doc-endnotes"><li>Note</li></ol>'
        '<section epub:type="footnotes"><h2>Notes</h2><p>n</p></section>'
    )

    assert sections == [("One", "One\na"), (None, "Note"), (None, "Notes\nn")]


def test_split_sections_falls_back_to_page_breaks() -> None:
    sections = _split("<p>a</p><mbp:pagebreak/><p>b</p><mbp:pagebreak></mbp:pagebreak>")

    assert sections == [(None, "a"), (None, "b")]


def test_split_sections_promotes_chapter_titles_without_headings() -> None:
    sections = _split(
        "<p>Preface text.</p><p>Chapter 1</p><p>a</p><p>CHAPTER 2</p><p>b</p>"
    )

    assert [label for label, _ in sections] == [None, "Chapter 1", "CHAPTER 2"]


def test_split_sections_keeps_image_only_parts_and_drops_empty_ones() -> None:
    sections = split_sections(
        _body("<p> </p><!-- x --><h1>One</h1><p>a</p><h1>Map</h1><img src='m.png'/>")
    )

    assert [s.label for s in sections] == ["One", "Map"]


def test_split_sections_without_any_break_keeps_one_section() -> None:
    assert _split("<p>Just text.</p>") == [(None, "Just text.")]


@pytest.mark.parametrize(
    ("html", "level"),
    [
        ("<h1>a</h1><h1>b</h1><h2>c</h2><h2>d</h2>", 1),
        ("<h1>a</h1><h2>c</h2><h2>d</h2>", 2),
        ("<h2>c</h2><h3>d</h3>", 2),
        ("<h1> </h1><h3>x</h3>", 3),
        ("<h4>a</h4><h4>b</h4>", None),
    ],
)
def test_heading_split_level(html: str, level: int | None) -> None:
    assert heading_split_level(_body(html)) == level


@pytest.mark.parametrize(
    ("levels", "depth"),
    [
        ([1, 1, 1], 1),
        ([1, 2, 2, 2], 2),
        ([1, 1, 2, 2], 2),
        ([1, 2, 3, 3], 3),
        ([1], 3),
        ([], 3),
    ],
)
def test_toc_depth(levels: list[int], depth: int) -> None:
    assert toc_depth(levels) == depth


def test_mark_toc_labels_targets_and_ignores_missing_ids() -> None:
    body = _body(f'<a id="a"></a><p id="b" {TOC_LABEL}="Kept">x</p>')

    mark_toc(body, {"a": "First", "b": "Other", "missing": "Gone"})

    assert body.find(id="a")[TOC_LABEL] == "First"  # ty: ignore[not-subscriptable]
    assert body.find(id="b")[TOC_LABEL] == "Kept"  # ty: ignore[not-subscriptable]


def test_relink_points_fragment_links_at_their_new_section() -> None:
    first = BeautifulSoup(
        '<body><a href="#n1">1</a><a href="#here">h</a><p id="here"/>'
        '<a href="other.html#n1">o</a><a href="#nowhere">x</a></body>',
        "html.parser",
    ).body
    second = BeautifulSoup('<body><p id="n1">Note</p></body>', "html.parser").body
    assert isinstance(first, Tag) and isinstance(second, Tag)

    relink([("section-001", first), ("section-002", second)])

    assert [link["href"] for link in first.find_all("a")] == [
        "section-002#n1",
        "#here",
        "other.html#n1",
        "#nowhere",
    ]
