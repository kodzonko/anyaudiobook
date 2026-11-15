"""Tests for finding headings in documents without heading markup."""

import pytest
from bs4 import BeautifulSoup

from anyaudiobook.markup import clean_body
from anyaudiobook.readers.headings import (
    class_font_sizes,
    is_heading_text,
    promote_headings,
)


@pytest.mark.parametrize(
    "text",
    [
        "Chapter 1",
        "CHAPTER XII",
        "Chapter Seven",
        "Chapter 3: The Return",
        "Chapter 4 The Boy Who Lived",
        "Part Two",
        "Book One",
        "Rozdział 1.",
        "Rozdział pierwszy",
        "Część druga",
        "Księga III — Powrót",
        "IV",
        "12.",
        "Prologue",
        "Epilog",
        "Epilogue: Ten Years Later",
        "Podziękowania",
        "Spis treści",
        "Acknowledgments",
    ],
)
def test_is_heading_text_recognises_titles(text: str) -> None:
    assert is_heading_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Part 2 of the plan was simple.",
        "Chapter and verse were quoted.",
        "One part of me wanted to stay",
        "Introduction to the problem",
        "Thanks.",
        '"Thanks"',
        "— Podziękowania",
        "It was a dark and stormy night.",
        "Chapter 1 " + "word " * 20,
    ],
)
def test_is_heading_text_rejects_sentences(text: str) -> None:
    assert not is_heading_text(text)


def test_class_font_sizes_reads_classes_in_px_and_pt() -> None:
    soup = BeautifulSoup(
        "<style>p.p1 {margin: 0; font: 24.0px Times} .c2, h3.big{font-size:15pt}"
        " p.plain {color: red} p {font-size: 9px}</style>",
        "html.parser",
    )

    assert class_font_sizes(soup) == {"p1": 24.0, "c2": 20.0, "big": 20.0}


def test_promote_headings_uses_font_sizes_then_title_patterns() -> None:
    soup = BeautifulSoup(
        "<style>.big{font-size:24px} .mid{font-size:16px} .body{font-size:12px}</style>"
        "<p class='big'>The Boy Who Lived</p>"
        f"<p class='body'>{'Text of the chapter, the bulk of the book. ' * 10}</p>"
        "<p class='mid'>A smaller heading</p>"
        "<p class='body'>Chapter 2</p>"
        f"<p class='big'>{'Too long to be a heading. ' * 5}</p>"
        "<div><p>Block wrapper is skipped</p></div>",
        "html.parser",
    )
    sizes = class_font_sizes(soup)
    body = clean_body(soup)

    promoted = promote_headings(body, sizes)

    assert promoted == 3
    assert [(tag.name, tag.get_text()) for tag in body.find_all(["h1", "h2"])] == [
        ("h1", "The Boy Who Lived"),
        ("h2", "A smaller heading"),
        ("h1", "Chapter 2"),
    ]
