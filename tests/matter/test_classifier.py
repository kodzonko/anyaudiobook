"""Tests for weighing front and back matter signals by position."""

from dataclasses import replace

import pytest

from anyaudiobook.matter.classifier import classify_documents
from anyaudiobook.matter.models import FilterOptions, MatterKind
from anyaudiobook.models import Document, Reference
from tests.matter.conftest import LONG_TEXT, DocumentFactory

K = MatterKind


def _kinds(
    documents: list[Document],
    short_page_words: int = 30,
    long_page_words: int = 1500,
) -> list[MatterKind]:
    """Classify documents with the given thresholds and return only the kinds."""
    options = FilterOptions(
        short_page_words=short_page_words, long_page_words=long_page_words
    )
    return [v.kind for v in classify_documents(documents, options)]


@pytest.fixture
def chapter(make_document: DocumentFactory) -> Document:
    """A plain, long chapter."""
    return make_document(f"<h1>Chapter</h1><p>{LONG_TEXT}</p>", "Text/ch1.xhtml")


def test_typical_book_keeps_only_main_text(make_document: DocumentFactory) -> None:
    documents = [
        make_document("<img src='cover.jpg'/>", "Text/cover.xhtml"),
        make_document("<h1>The Book</h1><p>Jane Doe</p>", "Text/title.xhtml"),
        make_document(
            "<p>Copyright © 2021 Jane Doe. All rights reserved.</p><p>ISBN 978-0</p>",
            "Text/x1.xhtml",
        ),
        make_document("<p>For Mum.</p>", "Text/x2.xhtml"),
        make_document(
            '<p><a href="ch1.xhtml">One</a></p>', "Text/nav.xhtml", is_nav=True
        ),
        make_document(f"<h1>Foreword</h1><p>{LONG_TEXT}</p>", "Text/foreword.xhtml"),
        make_document(f"<h1>Chapter 1</h1><p>{LONG_TEXT}</p>", "Text/ch1.xhtml"),
        make_document("<p>Part Two</p>", "Text/part2.xhtml"),
        make_document(f"<h1>Chapter 2</h1><p>{LONG_TEXT}</p>", "Text/ch2.xhtml"),
        make_document("<h1>Podziękowania</h1><p>Thanks to all.</p>", "Text/x3.xhtml"),
        make_document("<h1>Bio</h1><p>Jane lives in Kraków.</p>", "Text/about.xhtml"),
    ]

    assert _kinds(documents) == [
        K.EMPTY,
        K.TITLE_PAGE,
        K.COPYRIGHT,
        K.SHORT_PAGE,
        K.TOC,
        K.BODY,
        K.BODY,
        K.BODY,  # a short part page between chapters stays
        K.BODY,
        K.ACKNOWLEDGMENTS,
        K.ABOUT_AUTHOR,
    ]


def test_title_inside_main_text_skips_short_page_but_keeps_long_chapter(
    make_document: DocumentFactory, chapter: Document
) -> None:
    short_map = make_document("<h1>Mapa</h1><p>A map of the land.</p>", "Text/m1.xhtml")
    long_map = make_document(f"<h1>Mapa</h1><p>{LONG_TEXT}</p>", "Text/m2.xhtml")

    verdicts = classify_documents([chapter, short_map, long_map, chapter])

    assert [v.kind for v in verdicts] == [K.BODY, K.REFERENCE, K.BODY, K.BODY]
    assert "although" in verdicts[2].reason


def test_long_page_threshold_is_configurable(
    make_document: DocumentFactory, chapter: Document
) -> None:
    long_map = make_document(f"<h1>Mapa</h1><p>{LONG_TEXT}</p>", "Text/m.xhtml")
    documents = [chapter, long_map, chapter]

    assert _kinds(documents, long_page_words=5000)[1] is K.REFERENCE


def test_weak_hints_apply_only_outside_main_text(
    make_document: DocumentFactory, chapter: Document
) -> None:
    named_notes = make_document(f"<p>{LONG_TEXT}</p>", "Text/notes.xhtml")
    documents = [named_notes, chapter, named_notes, chapter, named_notes]

    assert _kinds(documents) == [K.NOTES, K.BODY, K.BODY, K.BODY, K.NOTES]


def test_bodymatter_landmark_marks_start_of_main_text(
    make_document: DocumentFactory,
) -> None:
    preface = make_document(f"<p>{LONG_TEXT}</p>", "Text/a.xhtml")
    motto = make_document("<p>To be or not to be.</p>", "Text/b.xhtml")
    first = make_document(
        f"<p>{LONG_TEXT}</p>",
        "Text/c.xhtml",
        references=(Reference("bodymatter"),),
    )

    unmarked = replace(first, references=())

    assert _kinds([preface, motto, first]) == [K.BODY, K.SHORT_PAGE, K.BODY]
    assert _kinds([preface, motto, unmarked]) == [K.BODY, K.BODY, K.BODY]


def test_book_without_clear_main_text_ignores_weak_hints(
    make_document: DocumentFactory,
) -> None:
    documents = [
        make_document("<p>Very short.</p>", "Text/title.xhtml"),
        make_document("<p>Also short.</p>", "Text/notes.xhtml"),
    ]

    assert _kinds(documents) == [K.BODY, K.BODY]


def test_non_linear_documents_are_skipped_with_the_best_known_kind(
    make_document: DocumentFactory, chapter: Document
) -> None:
    popup = make_document(f"<p>{LONG_TEXT}</p>", "Text/popup.xhtml", linear=False)
    notes = make_document(
        f"<h1>Przypisy</h1><p>{LONG_TEXT}</p>", "Text/x.xhtml", linear=False
    )

    verdicts = classify_documents([chapter, popup, notes])

    assert [v.kind for v in verdicts] == [K.BODY, K.AUXILIARY, K.NOTES]
    assert 'linear="no"' in verdicts[2].reason


def test_all_non_linear_spine_is_treated_as_linear(
    make_document: DocumentFactory,
) -> None:
    documents = [
        make_document(f"<p>{LONG_TEXT}</p>", f"Text/ch{n}.xhtml", linear=False)
        for n in range(2)
    ]

    assert _kinds(documents) == [K.BODY, K.BODY]


def test_short_page_threshold_is_configurable(
    make_document: DocumentFactory, chapter: Document
) -> None:
    epigraph = make_document("<p>" + " ".join(["word"] * 40) + "</p>", "Text/e.xhtml")

    assert _kinds([epigraph, chapter])[0] is K.BODY
    assert _kinds([epigraph, chapter], short_page_words=50)[0] is K.SHORT_PAGE


def test_unlisted_pages_before_first_listed_chapter_are_skipped(
    make_document: DocumentFactory,
) -> None:
    def listed(name: str) -> Document:
        return make_document(
            f"<p>{LONG_TEXT}</p>", f"Text/{name}.xhtml", toc_label=name
        )

    praise = make_document("<p>" + " ".join(["great"] * 100) + "</p>", "Text/a.xhtml")
    continuation = make_document(f"<p>{LONG_TEXT}</p>", "Text/b.xhtml")
    documents = [praise, listed("Preface"), listed("One"), continuation, listed("Two")]

    verdicts = classify_documents(documents)

    assert [v.kind for v in verdicts] == [K.UNLISTED, K.BODY, K.BODY, K.BODY, K.BODY]
    assert "table of contents" in verdicts[0].reason


def test_sparse_table_of_contents_does_not_decide_main_text_start(
    make_document: DocumentFactory,
) -> None:
    unlisted = [
        make_document(f"<p>{LONG_TEXT}</p>", f"Text/ch{n}.xhtml") for n in range(3)
    ]
    late = make_document(f"<p>{LONG_TEXT}</p>", "Text/ch9.xhtml", toc_label="Nine")

    assert _kinds([*unlisted, late]) == [K.BODY] * 4
