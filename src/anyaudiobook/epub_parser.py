"""Extract narratable chapters from EPUB files."""

import copy
import re
import warnings
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from anyaudiobook.markup import (
    extract_text,
    remove_unspoken,
    resolve_href,
    semantic_types,
    single_line,
)
from anyaudiobook.matter import (
    Decision,
    Document,
    FilterOptions,
    MatterKind,
    Reference,
    Verdict,
    classify_documents,
)
from anyaudiobook.models import BookContent

# Silence noisy ebooklib warnings that don't affect parsing.
warnings.filterwarnings(
    "ignore",
    message="In the future version we will turn default option ignore_ncx to True.",
)
warnings.filterwarnings(
    "ignore",
    message="This search incorrectly ignores the root element, and will be fixed in a future version.",
)


@dataclass(frozen=True, slots=True)
class ParsedBook:
    """A book split into chapters, with the reasoning behind the split."""

    chapters: list[BookContent]
    """The chapters to narrate, in reading order."""
    decisions: list[Decision]
    """One entry per spine document, narrated or not."""


def parse_heading(heading: Tag | None, fallback_title: str) -> tuple[int | None, str]:
    """Read the chapter number and title from a chapter's ``<h1>`` tag.

    The number and title come from a ``title="N. Title"`` attribute when it is
    present and well formed; otherwise the heading text, then ``fallback_title``,
    is used as the title and the number is None.

    Args:
        heading: The chapter's first ``<h1>`` tag, if any.
        fallback_title: Title to use when there is no heading.

    Returns:
        A ``(chapter_number, title)`` pair; ``chapter_number`` is None when the
        heading does not carry one.
    """
    if heading is None:
        return None, fallback_title

    attribute = heading.get("title")
    if isinstance(attribute, str):
        number, separator, title = " ".join(attribute.split()).partition(". ")
        if separator:
            title = title.replace("„", "").replace("”", "").strip()
            try:
                return int(number), title
            except ValueError:
                return None, title

    return None, single_line(heading) or fallback_title


def read_book(
    epub_path: str | Path, options: FilterOptions | None = None
) -> ParsedBook:
    """Split an EPUB file into narratable chapters, explaining each choice.

    Documents are read in spine (reading) order. Front and back matter is
    recognised by :func:`anyaudiobook.matter.classify_documents` and left out
    as ``options`` say; notes, note markers and page numbers are removed from
    the chapters that remain. Chapters without a number in their heading are
    numbered by their position among the narrated chapters.

    Args:
        epub_path: Path to the EPUB file.
        options: What to narrate; defaults to :class:`FilterOptions`.

    Returns:
        The chapters and one decision per spine document.
    """
    options = options or FilterOptions()
    documents = load_documents(epub.read_epub(str(epub_path)))
    verdicts = classify_documents(documents, options)
    include = _compile(options.include)
    exclude = _compile(options.exclude)

    chapters: list[BookContent] = []
    decisions: list[Decision] = []
    for position, (document, verdict) in enumerate(
        zip(documents, verdicts, strict=True), start=1
    ):
        heading = document.body.find("h1")
        number, title = parse_heading(
            heading if isinstance(heading, Tag) else None,
            document.toc_label or document.file_name,
        )
        narrate, reason = _choose(
            verdict, (document.file_name, title), options, include, exclude
        )
        decisions.append(
            Decision(
                position=position,
                file_name=document.file_name,
                title=title,
                kind=verdict.kind,
                reason=reason,
                narrate=narrate,
                word_count=document.word_count,
            )
        )
        if narrate:
            chapters.append(
                BookContent(
                    chapter_number=number if number is not None else len(chapters) + 1,
                    title=title,
                    content=narration_text(document, options),
                )
            )
    return ParsedBook(chapters=chapters, decisions=decisions)


def read_chapters(
    epub_path: str | Path, options: FilterOptions | None = None
) -> list[BookContent]:
    """Split an EPUB file into narratable chapters, see :func:`read_book`."""
    return read_book(epub_path, options).chapters


def narration_text(document: Document, options: FilterOptions) -> str:
    """Return the text to narrate for a document.

    Notes, note markers, page-break markers and navigation are removed (plus
    tables and captions if ``options`` say so). A document consisting only
    of such elements, e.g. a notes page the user chose to narrate, is read in
    full instead.
    """
    body = copy.copy(document.body)
    remove_unspoken(
        body, drop_tables=options.drop_tables, drop_captions=options.drop_captions
    )
    return extract_text(body) or document.text


def _compile(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    """Compile user patterns, ignoring case."""
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def _choose(
    verdict: Verdict,
    names: Sequence[str],
    options: FilterOptions,
    include: Sequence[re.Pattern[str]],
    exclude: Sequence[re.Pattern[str]],
) -> tuple[bool, str]:
    """Decide whether to narrate a document, applying the user's overrides.

    Args:
        verdict: The classifier's verdict.
        names: The document's file name and title, matched against patterns.
        options: The user's settings.
        include: Compiled ``options.include``.
        exclude: Compiled ``options.exclude``.

    Returns:
        Whether to narrate the document, and why.
    """
    if verdict.kind is MatterKind.EMPTY:
        return False, verdict.reason
    for pattern in exclude:
        if any(pattern.search(name) for name in names):
            return False, f"{verdict.reason}; excluded by {pattern.pattern!r}"
    for pattern in include:
        if any(pattern.search(name) for name in names):
            return True, f"{verdict.reason}; included by {pattern.pattern!r}"
    return verdict.kind not in options.skip, verdict.reason


def load_documents(book: epub.EpubBook) -> list[Document]:
    """Prepare a book's spine documents for classification.

    Args:
        book: The book, as read by ebooklib.

    Returns:
        The documents in reading order, with their TOC labels, guide and
        landmark entries and ``linear`` flags.
    """
    order = _reading_order(book)
    file_names = {item.get_name() for item, _ in order}
    references = _references(book)
    labels = _toc_labels(book, file_names)
    return [
        Document.from_html(
            item.get_name(),
            # Raw content: ``get_content()`` rebuilds the page and drops the
            # attributes of <body>, where ``epub:type`` often is.
            item.content,
            toc_label=labels.get(item.get_name()),
            linear=linear,
            is_nav=isinstance(item, epub.EpubNav),
            references=tuple(references.get(item.get_name(), ())),
        )
        for item, linear in order
    ]


def _reading_order(book: epub.EpubBook) -> list[tuple[epub.EpubItem, bool]]:
    """Return the book's documents in spine order with their ``linear`` flag.

    Falls back to manifest order when the spine lists no documents.
    """
    order: list[tuple[epub.EpubItem, bool]] = []
    for entry in book.spine:
        idref, *rest = entry if isinstance(entry, tuple) else (entry,)
        item = book.get_item_with_id(idref) if isinstance(idref, str) else idref
        if (
            isinstance(item, epub.EpubItem)
            and item.get_type() == ebooklib.ITEM_DOCUMENT
        ):
            order.append((item, not rest or rest[0] != "no"))
    if order:
        return order
    return [(item, True) for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]


def _references(book: epub.EpubBook) -> dict[str, list[Reference]]:
    """Collect EPUB 2 guide and EPUB 3 landmark entries by target document."""
    references: defaultdict[str, list[Reference]] = defaultdict(list)
    for entry in book.guide:
        href, kind = entry.get("href"), entry.get("type")
        if isinstance(href, str) and href and isinstance(kind, str) and kind:
            name, fragment = resolve_href("", href)
            references[name].append(Reference(kind.lower(), partial=bool(fragment)))

    for item in book.get_items():
        if not isinstance(item, epub.EpubNav):
            continue
        soup = BeautifulSoup(item.content, "html.parser")
        for nav in soup.find_all("nav"):
            if not isinstance(nav, Tag) or "landmarks" not in semantic_types(nav):
                continue
            for link in nav.find_all("a", href=True):
                href = link.get("href") if isinstance(link, Tag) else None
                if not isinstance(link, Tag) or not isinstance(href, str):
                    continue
                name, fragment = resolve_href(item.get_name(), href)
                for kind in semantic_types(link):
                    references[name].append(Reference(kind, partial=bool(fragment)))
    return references


def _toc_labels(book: epub.EpubBook, file_names: set[str]) -> dict[str, str]:
    """Map document names to their label in the book's table of contents.

    A label for the whole document wins over one for a fragment of it.
    """
    # NCX links are relative to the NCX file, nav links to the OPF directory.
    bases = [""] + [
        ncx.get_name() for ncx in book.get_items_of_type(ebooklib.ITEM_NAVIGATION)
    ]
    labels: dict[str, str] = {}
    whole: set[str] = set()
    for href, label in _walk_toc(book.toc):
        for base in bases:
            name, fragment = resolve_href(base, href)
            if name in file_names:
                break
        else:
            continue
        if name not in labels or (not fragment and name not in whole):
            labels[name] = label
        if not fragment:
            whole.add(name)
    return labels


def _walk_toc(entries: Iterable[object]) -> Iterator[tuple[str, str]]:
    """Yield ``(href, label)`` for every entry of an ebooklib TOC tree."""
    for entry in entries:
        if isinstance(entry, tuple | list):
            yield from _walk_toc(
                child
                for part in entry
                for child in (part if isinstance(part, list) else [part])
            )
        elif isinstance(entry, epub.Link | epub.Section):
            if entry.href and entry.title:
                yield entry.href, entry.title.strip()
        elif isinstance(entry, epub.EpubHtml) and entry.title:
            yield entry.file_name, entry.title.strip()
