"""Tests for the individual front and back matter signals."""

import pytest

from anyaudiobook.matter.models import MatterKind
from anyaudiobook.matter.signals import (
    content_verdict,
    filename_verdict,
    reference_hint,
    short_page_verdict,
    structural_verdict,
    title_verdict,
)
from anyaudiobook.models import Reference
from tests.matter.conftest import LONG_TEXT, DocumentFactory

BOOK_FILES = frozenset(f"Text/ch{number}.xhtml" for number in range(1, 7))


def _lines(template: str, count: int = 10) -> str:
    """Repeat a paragraph template, filling ``{n}`` with 1, 2, ..."""
    return "".join(template.format(n=n) for n in range(1, count + 1))


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (
            '<section epub:type="dedication"><p>Dla mamy</p></section>',
            MatterKind.DEDICATION,
        ),
        (
            f'<section role="doc-acknowledgments"><p>{LONG_TEXT}</p></section>',
            MatterKind.ACKNOWLEDGMENTS,
        ),
        (
            '<div><section epub:type="copyright-page"><p>© 2020</p></section></div>',
            MatterKind.COPYRIGHT,
        ),
        (
            (
                f'<section epub:type="chapter"><p>{LONG_TEXT}</p>'
                '<section epub:type="footnotes"><p>A note.</p></section></section>'
            ),
            MatterKind.BODY,
        ),
        (
            (
                f'<section epub:type="epigraph"><section epub:type="chapter">'
                f"<p>{LONG_TEXT}</p></section></section>"
            ),
            MatterKind.BODY,
        ),
    ],
)
def test_structural_verdict_reads_markup_covering_most_text(
    make_document: DocumentFactory, body: str, kind: MatterKind
) -> None:
    verdict = structural_verdict(make_document(body))
    assert verdict is not None
    assert verdict.kind is kind


def test_structural_verdict_ignores_small_marked_elements(
    make_document: DocumentFactory,
) -> None:
    body = f'<nav epub:type="toc"><a href="a.xhtml">A</a></nav><p>{LONG_TEXT}</p>'
    assert structural_verdict(make_document(body)) is None


def test_structural_verdict_flags_navigation_document(
    make_document: DocumentFactory,
) -> None:
    verdict = structural_verdict(make_document(is_nav=True))
    assert verdict is not None
    assert verdict.kind is MatterKind.TOC


@pytest.mark.parametrize(
    ("reference", "kind"),
    [
        (Reference("copyright-page"), MatterKind.COPYRIGHT),
        (Reference("notes"), MatterKind.NOTES),
        (Reference("foreword"), MatterKind.BODY),
    ],
)
def test_structural_verdict_trusts_guide_entries_for_whole_documents(
    make_document: DocumentFactory, reference: Reference, kind: MatterKind
) -> None:
    verdict = structural_verdict(make_document(references=(reference,)))
    assert verdict is not None
    assert verdict.kind is kind
    assert "guide" in verdict.reason


def test_partial_guide_entries_are_only_a_hint(make_document: DocumentFactory) -> None:
    document = make_document(references=(Reference("index", partial=True),))
    hint = reference_hint(document)

    assert structural_verdict(document) is None
    assert hint is not None
    assert hint.kind is MatterKind.INDEX


@pytest.mark.parametrize(
    "references",
    [(), (Reference("text", partial=True),), (Reference("chapter", partial=True),)],
)
def test_reference_hint_ignores_main_text_and_unknown_types(
    make_document: DocumentFactory, references: tuple[Reference, ...]
) -> None:
    assert reference_hint(make_document(references=references)) is None


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (
            (
                "<p>Tytuł oryginału: The Book</p><p>Copyright © 2020 by Author</p>"
                "<p>Redakcja: Anna Nowak</p><p>Korekta: Jan Kowalski</p>"
                "<p>ISBN 978-83-000-0000-0</p><p>Wydawnictwo XYZ, www.xyz.pl</p>"
            ),
            MatterKind.COPYRIGHT,
        ),
        (
            (
                "<p>Copyright © 2021 Jane Doe. All rights reserved.</p>"
                "<p>First published in 2021. Printed in the USA.</p>"
            ),
            MatterKind.COPYRIGHT,
        ),
        (_lines("<p>Kowalski Jan, {n}, 45–47</p>"), MatterKind.INDEX),
        (_lines('<p><a href="ch{n}.xhtml">Chapter {n}</a></p>', 5), MatterKind.TOC),
        (_lines("<p>Rozdział {n} ........ {n}5</p>", 6), MatterKind.TOC),
        (
            "".join(
                f"<p>term {n} {page}</p>"
                for n, page in enumerate([40, 7, 93, 12, 3, 77])
            ),
            MatterKind.INDEX,
        ),
        (
            _lines(
                '<p><a href="ch{n}.xhtml#ref{n}">{n}</a> A note explaining something '
                "said in the chapter at some length.</p>",
                4,
            ),
            MatterKind.NOTES,
        ),
        (
            _lines(
                '<aside epub:type="endnote"><p>Note {n} about the text.</p></aside>', 3
            ),
            MatterKind.NOTES,
        ),
        (
            _lines("<p>Another book, ISBN 978-0-00-00000{n}-0</p>", 3),
            MatterKind.ADVERTISEMENT,
        ),
        (
            _lines('<p><a href="https://shop.example/{n}">Shop {n}</a></p>', 3),
            MatterKind.ADVERTISEMENT,
        ),
    ],
)
def test_content_verdict_recognises_matter_by_shape(
    make_document: DocumentFactory, body: str, kind: MatterKind
) -> None:
    verdict = content_verdict(make_document(body), BOOK_FILES)
    assert verdict is not None
    assert verdict.kind is kind


@pytest.mark.parametrize(
    "body",
    [
        f"<p>{LONG_TEXT}</p>",
        "<p>He drew a © sign on the wall and left.</p>",
        f"<p>Copyright © 2020. ISBN 978-0. {LONG_TEXT}</p>",
        # A technical chapter citing books in its references.
        f"<p>{LONG_TEXT}</p>" + _lines("<p>Book {n}. ISBN 978-0-00-00000{n}-0</p>", 6),
        f"<p>{LONG_TEXT}</p>"
        + _lines('<p><a href="https://example.com/{n}">x</a></p>', 3),
    ],
)
def test_content_verdict_leaves_ordinary_text_alone(
    make_document: DocumentFactory, body: str
) -> None:
    assert content_verdict(make_document(body), BOOK_FILES) is None


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("Spis treści:", MatterKind.TOC),
        ("Podziękowania", MatterKind.ACKNOWLEDGMENTS),
        ("ACKNOWLEDGEMENTS", MatterKind.ACKNOWLEDGMENTS),
        ("3. Przypisy", MatterKind.NOTES),
        ("O autorze", MatterKind.ABOUT_AUTHOR),
        ("Also by Jane Doe", MatterKind.ADVERTISEMENT),
        ("Indeks nazwisk", MatterKind.INDEX),
        ("Skorowidz", MatterKind.INDEX),
        ("Drzewo genealogiczne", MatterKind.REFERENCE),
        ("Od wydawcy", MatterKind.EDITORIAL_NOTE),
        ("Notes from Underground", None),
        ("Rozdział 1", None),
        ("Index cards", None),
        ("Opinie o książce Przetwarzanie języka", MatterKind.ADVERTISEMENT),
        ("Rozdział 1.<br/>Początek", None),
        ("Spis<br/>treści", MatterKind.TOC),
    ],
)
def test_title_verdict(
    make_document: DocumentFactory, title: str, kind: MatterKind | None
) -> None:
    verdict = title_verdict(make_document(f"<h1>{title}</h1><p>{LONG_TEXT}</p>"))
    assert (verdict.kind if verdict else None) is kind


def test_title_verdict_uses_toc_label(make_document: DocumentFactory) -> None:
    verdict = title_verdict(
        make_document("<p>No heading</p>", toc_label="Bibliografia")
    )
    assert verdict is not None
    assert verdict.kind is MatterKind.BIBLIOGRAPHY


@pytest.mark.parametrize(
    ("file_name", "kind"),
    [
        ("Text/Acknowledgements.xhtml", MatterKind.ACKNOWLEDGMENTS),
        ("OEBPS/copyright.html", MatterKind.COPYRIGHT),
        ("Text/przypisy.xhtml", MatterKind.NOTES),
        ("Text/dedykacja.xhtml", MatterKind.DEDICATION),
        ("about_the_author.xhtml", MatterKind.ABOUT_AUTHOR),
        ("Text/spis_tresci.xhtml", MatterKind.TOC),
        ("Text/Źródła.xhtml", MatterKind.BIBLIOGRAPHY),
        ("index_split_000.html", None),
        ("Text/ch01.xhtml", None),
        ("Text/Section0003.xhtml", None),
    ],
)
def test_filename_verdict(
    make_document: DocumentFactory, file_name: str, kind: MatterKind | None
) -> None:
    verdict = filename_verdict(make_document(file_name=file_name))
    assert (verdict.kind if verdict else None) is kind


@pytest.mark.parametrize(
    ("body", "flagged"),
    [("<p>Dla mamy</p>", True), ("", False), (f"<p>{LONG_TEXT}</p>", False)],
)
def test_short_page_verdict(
    make_document: DocumentFactory, body: str, flagged: bool
) -> None:
    verdict = short_page_verdict(make_document(body), 30)
    assert (verdict is not None) is flagged
    if verdict:
        assert verdict.kind is MatterKind.SHORT_PAGE
