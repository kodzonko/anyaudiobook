"""Combine the signals of :mod:`anyaudiobook.matter.signals` into verdicts.

Signals have three strengths:

* **Decisive** — the EPUB's own markup, guide and landmarks, and content
  shape (copyright pages, indexes, notes, ...). They apply anywhere.
* **Title** — a heading or TOC label such as "Podziękowania". Applies before
  and after the main text, and inside it only to pages shorter than
  :attr:`FilterOptions.long_page_words`, so a long chapter called "Mapa"
  stays.
* **Weak** — file names, guide entries pointing inside a document and very
  short pages. Apply only before and after the main text.

The main text runs from the first to the last document no signal objects
to. When the table of contents lists most of those documents, it starts at
the first listed one, and unlisted pages before it (half-titles, epigraphs,
praise) are skipped as :attr:`MatterKind.UNLISTED`. The book's
``bodymatter`` landmark (or ``text`` guide entry), when present, marks the
start instead.
"""

from collections.abc import Sequence

from anyaudiobook.matter.keywords import MAIN_TEXT_START_TYPES
from anyaudiobook.matter.models import FilterOptions, MatterKind, Verdict
from anyaudiobook.matter.signals import (
    content_verdict,
    filename_verdict,
    reference_hint,
    short_page_verdict,
    structural_verdict,
    title_verdict,
)
from anyaudiobook.models import Document


def classify_documents(
    documents: Sequence[Document], options: FilterOptions | None = None
) -> list[Verdict]:
    """Decide what each document of a book's spine is.

    Args:
        documents: The book's documents in reading order.
        options: Thresholds to use; defaults to :class:`FilterOptions`.

    Returns:
        One verdict per document, in the same order.
    """
    options = options or FilterOptions()
    book_files = frozenset(document.file_name for document in documents)
    decisive = [_decisive_verdict(document, book_files) for document in documents]
    titles = [title_verdict(document) for document in documents]
    weak = [
        reference_hint(document)
        or filename_verdict(document)
        or short_page_verdict(document, options.short_page_words)
        for document in documents
    ]
    # A book whose every document is non-linear is broken, not all extras.
    honour_linear = any(document.linear for document in documents)
    main_text, toc_guides = _main_text_span(
        documents, decisive, titles, weak, honour_linear
    )

    verdicts: list[Verdict] = []
    for position, document in enumerate(documents):
        if honour_linear and not document.linear:
            verdicts.append(
                _non_linear(decisive[position], titles[position], weak[position])
            )
            continue
        verdicts.append(
            _settle(
                document,
                decisive[position],
                titles[position],
                weak[position],
                inside_main_text=position in main_text,
                unlisted_front_matter=(
                    toc_guides and position < main_text.start and not document.toc_label
                ),
                long_page_words=options.long_page_words,
            )
        )
    return verdicts


def _decisive_verdict(document: Document, book_files: frozenset[str]) -> Verdict | None:
    """Return the verdict of the signals that apply anywhere in the book."""
    if not document.text:
        return Verdict(MatterKind.EMPTY, "no text")
    return structural_verdict(document) or content_verdict(document, book_files)


def _main_text_span(
    documents: Sequence[Document],
    decisive: Sequence[Verdict | None],
    titles: Sequence[Verdict | None],
    weak: Sequence[Verdict | None],
    honour_linear: bool,
) -> tuple[range, bool]:
    """Find the documents forming the book's main text.

    When nothing looks like main text, the whole book is returned, so that
    weak signals are not trusted to remove everything.

    Returns:
        The positions of the main text, and whether the table of contents
        lists enough of it to decide where it starts.
    """
    candidates = [
        position
        for position, (document, verdict, title, hint) in enumerate(
            zip(documents, decisive, titles, weak, strict=True)
        )
        if (document.linear or not honour_linear)
        and (
            verdict.kind is MatterKind.BODY
            if verdict is not None
            else title is None and hint is None
        )
    ]
    if not candidates:
        return range(len(documents)), False
    listed = [position for position in candidates if documents[position].toc_label]
    toc_guides = bool(listed) and len(listed) * 2 >= len(candidates)
    first = listed[0] if toc_guides else candidates[0]
    last = candidates[-1]
    start = next(
        (
            position
            for position, document in enumerate(documents)
            if any(ref.type in MAIN_TEXT_START_TYPES for ref in document.references)
        ),
        first,
    )
    return range(start if start <= last else first, last + 1), toc_guides


def _non_linear(
    decisive: Verdict | None, title: Verdict | None, weak: Verdict | None
) -> Verdict:
    """Return the verdict for a document the spine marks ``linear="no"``."""
    reason = 'the spine marks it linear="no"'
    specific = next(
        (
            verdict
            for verdict in (decisive, title, weak)
            if verdict is not None and verdict.kind is not MatterKind.BODY
        ),
        None,
    )
    if specific is None:
        return Verdict(MatterKind.AUXILIARY, reason)
    return Verdict(specific.kind, f"{specific.reason}; {reason}")


def _settle(
    document: Document,
    decisive: Verdict | None,
    title: Verdict | None,
    weak: Verdict | None,
    *,
    inside_main_text: bool,
    unlisted_front_matter: bool,
    long_page_words: int,
) -> Verdict:
    """Weigh one document's signals by its position in the book."""
    if decisive is not None:
        return decisive
    if title is not None and (
        not inside_main_text or document.word_count < long_page_words
    ):
        return title
    if weak is not None and not inside_main_text:
        return weak
    if unlisted_front_matter:
        return Verdict(
            MatterKind.UNLISTED,
            "before the main text and missing from the table of contents",
        )
    ignored = title or weak
    if ignored is None:
        return Verdict(MatterKind.BODY, "main text")
    return Verdict(MatterKind.BODY, f"main text, although {ignored.reason}")
