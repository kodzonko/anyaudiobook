"""Words and markup values that identify front and back matter.

Titles and file names are compared after :func:`normalize`, so the phrases
below may be written naturally, with diacritics, capitals and punctuation.
"""

import re
import unicodedata

from anyaudiobook.matter.models import MatterKind as K

_NON_WORD = re.compile(r"[\W_]+")
_LEADING_NUMBER = re.compile(r"^\d+\s+")
_LETTERS = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O"})


def fold(text: str) -> str:
    """Lowercase ``text`` and strip its diacritics (``Źródła`` → ``zrodla``)."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_LETTERS))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def normalize(title: str) -> str:
    """Reduce a title to lowercase words for comparison.

    Diacritics, punctuation and a leading chapter number are dropped:
    ``"7. Spis treści:"`` becomes ``"spis tresci"``.
    """
    return _LEADING_NUMBER.sub("", _NON_WORD.sub(" ", fold(title)).strip())


_TITLES: dict[K, tuple[str, ...]] = {
    K.COVER: ("cover", "okładka"),
    K.TITLE_PAGE: (
        "title page",
        "half title",
        "half title page",
        "strona tytułowa",
        "karta tytułowa",
    ),
    K.TOC: ("contents", "table of contents", "toc", "spis treści", "spis rzeczy"),
    K.COPYRIGHT: (
        "copyright",
        "copyright page",
        "colophon",
        "credits",
        "imprint",
        "impressum",
        "kolofon",
        "prawa autorskie",
        "strona redakcyjna",
        "karta redakcyjna",
        "stopka redakcyjna",
        "metryczka",
        "informacje o wydaniu",
    ),
    K.DEDICATION: ("dedication", "dedykacja"),
    K.EPIGRAPH: ("epigraph", "motto"),
    K.EDITORIAL_NOTE: (
        "publisher's note",
        "a note from the publisher",
        "note from the publisher",
        "editor's note",
        "a note on the text",
        "note on the text",
        "translator's note",
        "od wydawcy",
        "od wydawnictwa",
        "nota wydawcy",
        "nota wydawnicza",
        "nota wydawnictwa",
        "słowo od wydawcy",
        "nota redakcyjna",
        "nota edytorska",
        "od redakcji",
        "nota od redakcji",
        "od tłumacza",
        "nota tłumacza",
        "nota od tłumacza",
        "słowo od tłumacza",
    ),
    K.ACKNOWLEDGMENTS: (
        "acknowledgments",
        "acknowledgements",
        "thanks",
        "podziękowania",
        "słowo podziękowania",
    ),
    K.NOTES: (
        "notes",
        "endnotes",
        "footnotes",
        "chapter notes",
        "przypisy",
        "przypisy końcowe",
        "przypisy autora",
        "przypisy tłumacza",
    ),
    K.INDEX: ("index",),
    K.BIBLIOGRAPHY: (
        "bibliography",
        "selected bibliography",
        "sources",
        "notes on sources",
        "references",
        "works cited",
        "further reading",
        "suggested reading",
        "bibliografia",
        "wybrana bibliografia",
        "źródła",
        "literatura",
        "wybrana literatura",
        "lektury uzupełniające",
    ),
    K.GLOSSARY: (
        "glossary",
        "abbreviations",
        "list of abbreviations",
        "słowniczek",
        "słownik",
        "słownik terminów",
        "słowniczek terminów",
        "skróty",
        "wykaz skrótów",
    ),
    K.LIST_OF_FIGURES: (
        "illustrations",
        "list of illustrations",
        "list of figures",
        "list of maps",
        "list of tables",
        "illustration credits",
        "picture credits",
        "photo credits",
        "ilustracje",
        "spis ilustracji",
        "lista ilustracji",
        "spis map",
        "spis tabel",
        "źródła ilustracji",
        "źródła fotografii",
        "źródła zdjęć",
    ),
    K.REFERENCE: (
        "map",
        "maps",
        "family tree",
        "family trees",
        "genealogy",
        "chronology",
        "timeline",
        "dramatis personae",
        "cast of characters",
        "list of characters",
        "mapa",
        "mapy",
        "drzewo genealogiczne",
        "drzewa genealogiczne",
        "chronologia",
        "kalendarium",
        "oś czasu",
        "lista postaci",
        "spis postaci",
        "postacie",
        "bohaterowie",
    ),
    K.ABOUT_AUTHOR: (
        "about the author",
        "about the authors",
        "about the translator",
        "about the illustrator",
        "o autorze",
        "o autorce",
        "o autorach",
        "o tłumaczu",
        "o tłumaczce",
        "nota biograficzna",
        "nota o autorze",
    ),
    K.ADVERTISEMENT: (
        "praise",
        "advance praise",
        "newsletter",
        "coming soon",
        "polecamy",
        "zapowiedź",
        "zapowiedzi",
        "inne książki autora",
        "inne książki autorki",
        "tego autora",
        "tej autorki",
        "w tej serii",
        "w serii",
        "pytania do dyskusji",
        "opinie",
        "recenzje",
        "reviews",
    ),
}
"""Whole titles of front and back matter."""

_TITLE_PREFIXES: dict[K, tuple[str, ...]] = {
    K.INDEX: ("index of", "indeks", "skorowidz"),
    K.BIBLIOGRAPHY: ("bibliography", "bibliografia"),
    K.ABOUT_AUTHOR: ("about the author",),
    K.ADVERTISEMENT: (
        "also by",
        "also available",
        "by the same author",
        "more from",
        "more books by",
        "praise for",
        "what people are saying",
        "what readers are saying",
        "opinie o",
        "opinie czytelników",
        "excerpt from",
        "read an excerpt",
        "sneak peek",
        "preview of",
        "sign up",
        "reading group guide",
        "discussion questions",
        "książki tego autora",
        "książki tej autorki",
        "tego samego autora",
        "tej samej autorki",
        "przeczytaj fragment",
        "fragment książki",
        "zapowiedź",
    ),
}
"""Title beginnings of front and back matter, followed by more words."""

TITLE_PHRASES: dict[str, K] = {
    normalize(phrase): kind for kind, phrases in _TITLES.items() for phrase in phrases
}
"""Normalised whole titles mapped to the kind they identify."""

TITLE_PREFIXES: tuple[tuple[str, K], ...] = tuple(
    (normalize(prefix), kind)
    for kind, prefixes in _TITLE_PREFIXES.items()
    for prefix in prefixes
)
"""Normalised title beginnings and the kind they identify."""

_FILE_NAMES: dict[K, tuple[str, ...]] = {
    K.COVER: ("cover", "okladka"),
    K.TITLE_PAGE: ("title", "titlepage", "halftitle", "tytul", "tytulowa"),
    K.TOC: ("toc", "nav", "contents", "spis"),
    K.COPYRIGHT: (
        "copyright",
        "colophon",
        "kolofon",
        "imprint",
        "impressum",
        "credits",
        "legal",
        "rights",
        "redakcyj",
        "metryczka",
    ),
    K.DEDICATION: ("dedication", "dedykacja"),
    K.EPIGRAPH: ("epigraph", "motto"),
    K.EDITORIAL_NOTE: ("publisher", "wydawca", "wydawcy", "redakcji", "tlumacza"),
    K.ACKNOWLEDGMENTS: ("ack", "acknowledg", "thanks", "podziekowania"),
    K.NOTES: ("notes", "footnote", "endnote", "przypis"),
    K.INDEX: ("indeks", "skorowidz"),
    K.BIBLIOGRAPHY: (
        "biblio",
        "bibliograf",
        "references",
        "sources",
        "zrodla",
        "literatura",
    ),
    K.GLOSSARY: ("glossary", "slowniczek", "slownik", "abbreviations", "skroty"),
    K.LIST_OF_FIGURES: ("loi", "illustrations", "ilustrac"),
    K.REFERENCE: (
        "map",
        "maps",
        "mapa",
        "mapy",
        "chronolog",
        "timeline",
        "kalendarium",
        "genealog",
        "familytree",
        "drzewo",
        "dramatis",
        "postaci",
        "bohaterowie",
    ),
    K.ABOUT_AUTHOR: ("about", "bio", "abouttheauthor", "oautorze", "oautorce"),
    K.ADVERTISEMENT: (
        "ads",
        "advert",
        "promo",
        "polecamy",
        "zapowiedz",
        "newsletter",
        "alsoby",
        "teaser",
        "excerpt",
        "preview",
        "signup",
        "reklama",
    ),
}
"""File name words of front and back matter, already normalised.

Words of six or more letters also match inside longer names
(``acknowledg`` matches ``Acknowledgements.xhtml``); shorter ones only match
whole words. ``index`` is deliberately missing: ebook converters name the
main text ``index_split_000.html`` and so on.
"""

FILE_NAME_WORDS: dict[str, K] = {
    word: kind for kind, words in _FILE_NAMES.items() for word in words
}
"""File name words mapped to the kind they identify."""

MIN_SUBSTRING_LENGTH = 6
"""File name words this long also match inside longer names."""

SEMANTIC_KINDS: dict[str, K] = {
    "cover": K.COVER,
    "doc-cover": K.COVER,
    "titlepage": K.TITLE_PAGE,
    "halftitlepage": K.TITLE_PAGE,
    "title-page": K.TITLE_PAGE,
    "toc": K.TOC,
    "doc-toc": K.TOC,
    "landmarks": K.TOC,
    "page-list": K.TOC,
    "doc-pagelist": K.TOC,
    "copyright-page": K.COPYRIGHT,
    "colophon": K.COPYRIGHT,
    "doc-colophon": K.COPYRIGHT,
    "imprint": K.COPYRIGHT,
    "imprimatur": K.COPYRIGHT,
    "credits": K.COPYRIGHT,
    "other-credits": K.COPYRIGHT,
    "doc-credits": K.COPYRIGHT,
    "dedication": K.DEDICATION,
    "doc-dedication": K.DEDICATION,
    "epigraph": K.EPIGRAPH,
    "doc-epigraph": K.EPIGRAPH,
    "errata": K.EDITORIAL_NOTE,
    "doc-errata": K.EDITORIAL_NOTE,
    "revision-history": K.EDITORIAL_NOTE,
    "acknowledgments": K.ACKNOWLEDGMENTS,
    "acknowledgements": K.ACKNOWLEDGMENTS,
    "doc-acknowledgments": K.ACKNOWLEDGMENTS,
    "notes": K.NOTES,
    "endnotes": K.NOTES,
    "footnotes": K.NOTES,
    "rearnotes": K.NOTES,
    "doc-endnotes": K.NOTES,
    "index": K.INDEX,
    "doc-index": K.INDEX,
    "bibliography": K.BIBLIOGRAPHY,
    "doc-bibliography": K.BIBLIOGRAPHY,
    "glossary": K.GLOSSARY,
    "doc-glossary": K.GLOSSARY,
    "loi": K.LIST_OF_FIGURES,
    "lot": K.LIST_OF_FIGURES,
    "loa": K.LIST_OF_FIGURES,
    "lov": K.LIST_OF_FIGURES,
    "contributors": K.ABOUT_AUTHOR,
    "seriespage": K.ADVERTISEMENT,
}
"""``epub:type``/``role`` tokens and EPUB 2 guide types of front and back
matter. Guide types and landmarks share this table with markup tokens."""

MAIN_TEXT_TYPES: frozenset[str] = frozenset(
    {
        "afterword",
        "chapter",
        "conclusion",
        "epilogue",
        "foreword",
        "introduction",
        "part",
        "preamble",
        "preface",
        "prologue",
        "volume",
        "doc-afterword",
        "doc-chapter",
        "doc-conclusion",
        "doc-epilogue",
        "doc-foreword",
        "doc-introduction",
        "doc-part",
        "doc-preface",
        "doc-prologue",
    }
)
"""``epub:type``/``role`` tokens and guide types of narratable main text.

``bodymatter``, ``frontmatter`` and ``backmatter`` are missing on purpose:
they are too broad (a foreword is front matter, notes may be marked body
matter) to decide anything on their own."""

MAIN_TEXT_START_TYPES: frozenset[str] = frozenset({"bodymatter", "text", "start"})
"""Guide and landmark types marking where the main text begins."""
