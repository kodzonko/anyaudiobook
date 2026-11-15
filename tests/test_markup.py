"""Tests for XHTML helpers: semantic markup, cleanup and text extraction."""

import pytest
from bs4 import BeautifulSoup, Tag

from anyaudiobook.markup import (
    class_names,
    extract_text,
    heading_titles,
    is_external,
    is_note_markup,
    parse_html,
    remove_unspoken,
    resolve_href,
    semantic_types,
    single_line,
)


def _tag(html: str) -> Tag:
    """Parse an HTML snippet and return its first element."""
    tag = BeautifulSoup(html, "html.parser").find(True)
    assert isinstance(tag, Tag)
    return tag


def _cleaned(body: str, **options: bool) -> str:
    """Return the narratable text of ``body`` after removing unspoken parts."""
    root = parse_html(f"<html><body>{body}</body></html>")
    remove_unspoken(root, **options)
    return extract_text(root)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<section epub:type="Chapter bodymatter">', {"chapter", "bodymatter"}),
        ('<section role="doc-endnotes">', {"doc-endnotes"}),
        (
            '<aside epub:type="footnote" role="doc-footnote">',
            {"footnote", "doc-footnote"},
        ),
        ("<section>", set()),
    ],
)
def test_semantic_types_reads_epub_type_and_role(html: str, expected: set[str]) -> None:
    assert semantic_types(_tag(html)) == expected


def test_class_names_lists_classes() -> None:
    assert class_names(_tag('<p class="a  b">')) == ["a", "b"]
    assert class_names(_tag("<p>")) == []


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<a epub:type="noteref">', True),
        ('<div class="przypis">', True),
        ('<p class="calibre footnote-text">', True),
        ('<p class="note">', False),
        ("<p>", False),
    ],
)
def test_is_note_markup(html: str, expected: bool) -> None:
    assert is_note_markup(_tag(html)) is expected


def test_parse_html_returns_body_without_head_scripts_or_styles() -> None:
    root = parse_html(
        "<html><head><title>Book title</title></head>"
        "<body><p>Keep</p><script>drop()</script><style>p {}</style></body></html>"
    )
    assert extract_text(root) == "Keep"


def test_parse_html_without_body_keeps_everything() -> None:
    assert extract_text(parse_html("<p>Loose</p>")) == "Loose"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<h1>Title</h1><p>Body</p>", "Title\nBody"),
        ("<p>Hello <em>wide</em> world!</p>", "Hello wide world!"),
        ("<p>Wrapped\n   source   line</p>", "Wrapped source line"),
        ("<p>Line one<br/>Line two</p>", "Line one\nLine two"),
        ("<div>Intro<p>Para</p>Tail</div>", "Intro\nPara\nTail"),
        ("<p>Seen<!-- hidden --></p>", "Seen"),
        ("<p>non breaking</p>", "non breaking"),
        ("<ul><li>One</li><li>Two</li></ul>", "One\nTwo"),
        ("<p> </p><p></p>", ""),
    ],
)
def test_extract_text_puts_each_block_on_its_own_line(body: str, expected: str) -> None:
    assert extract_text(parse_html(f"<html><body>{body}</body></html>")) == expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('<h2 class="x">Chapter <em>One</em></h2>', ["Chapter One"]),
        ('<h1 title="3. Three">Three</h1>', ["Three", "3. Three"]),
        ("<p>No heading</p>", []),
        ("<h3> </h3>", []),
    ],
)
def test_heading_titles(body: str, expected: list[str]) -> None:
    assert heading_titles(parse_html(body)) == expected


@pytest.mark.parametrize(
    ("base", "href", "expected"),
    [
        ("Text/ch1.xhtml", "ch2.xhtml", ("Text/ch2.xhtml", "")),
        ("Text/ch1.xhtml", "../notes.xhtml#n1", ("notes.xhtml", "n1")),
        ("Text/ch1.xhtml", "#fn3", ("Text/ch1.xhtml", "fn3")),
        ("", "Text/My%20Chapter.xhtml", ("Text/My Chapter.xhtml", "")),
    ],
)
def test_resolve_href(base: str, href: str, expected: tuple[str, str]) -> None:
    assert resolve_href(base, href) == expected


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("https://example.com", True),
        ("mailto:a@b.c", True),
        ("www.example.com", True),
        ("ch2.xhtml#x", False),
        ("#fn1", False),
    ],
)
def test_is_external(href: str, expected: bool) -> None:
    assert is_external(href) is expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('<p>War<a epub:type="noteref" href="#n1">1</a> ended.</p>', "War ended."),
        ('<p>War<a role="doc-noteref" href="#n1">1</a> ended.</p>', "War ended."),
        ("<p>The war ended<sup>12</sup>.</p>", "The war ended."),
        ("<p>The war ended.<sup>[3]</sup></p>", "The war ended."),
        ("<p>Exactly 10<sup>6</sup> cells.</p>", "Exactly 106 cells."),
        ('<p>In 1945<a href="#fn3"><sup>3</sup></a>.</p>', "In 1945."),
        ('<p>Ended<a href="notes.xhtml#n2">[2]</a>.</p>', "Ended."),
        ('<p>Ended<a href="#x">*</a>.</p>', "Ended."),
        ('<p>Ended<a href="#fn4" id="fnref4">4</a>.</p>', "Ended."),
        ('<p>See chapter <a href="ch2.xhtml#ch2">2</a>.</p>', "See chapter 2."),
        (
            '<p>Text.</p><aside epub:type="footnote"><p>A note.</p></aside>',
            "Text.",
        ),
        ('<p>Text.</p><div class="przypisy"><p>1. Note.</p></div>', "Text."),
        (
            '<p>Before<span epub:type="pagebreak" title="12">12</span> after.</p>',
            "Before after.",
        ),
        ('<nav epub:type="toc"><a href="a.xhtml">A</a></nav><p>Text.</p>', "Text."),
        (
            '<p>Text.</p><section epub:type="footnotes"><p>Note.</p></section>',
            "Text.",
        ),
        ("<table><tr><td>Cell</td></tr></table>", "Cell"),
        ("<figure><img/><figcaption>Map</figcaption></figure>", "Map"),
    ],
)
def test_remove_unspoken_drops_notes_markers_and_navigation(
    body: str, expected: str
) -> None:
    assert _cleaned(body) == expected


@pytest.mark.parametrize(
    ("body", "option"),
    [
        ("<p>Text.</p><table><tr><td>Cell</td></tr></table>", "drop_tables"),
        ("<p>Text.</p><figure><figcaption>Map</figcaption></figure>", "drop_captions"),
        ("<p>Text.</p><table><caption>Data</caption></table>", "drop_captions"),
    ],
)
def test_remove_unspoken_optionally_drops_tables_and_captions(
    body: str, option: str
) -> None:
    assert _cleaned(body, **{option: True}) == "Text."


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<h1>Rozdział 1.<br/>Początek</h1>", "Rozdział 1. Początek"),
        ("<h1>Rozdział 2.\n    Dalej</h1>", "Rozdział 2. Dalej"),
        ("<h1>Chap<em>ter</em> 3</h1>", "Chapter 3"),
    ],
)
def test_single_line_joins_heading_lines(html: str, expected: str) -> None:
    assert single_line(_tag(html)) == expected
