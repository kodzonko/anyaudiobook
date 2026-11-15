"""Find chapter headings in documents that do not mark them up.

Plain text, Word files without heading styles, old Kindle books and HTML
exported by word processors show headings only as short lines or bigger
fonts. Turning those into ``<h1>``/``<h2>`` lets every format share the
same splitting (:mod:`anyaudiobook.readers.splitting`) and the same front
and back matter detection.
"""

import re
from collections import Counter
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

from anyaudiobook.markup import BLOCK_TAGS, class_names, single_line, text_length
from anyaudiobook.matter.keywords import TITLE_PHRASES, fold, normalize

MAX_HEADING_LENGTH = 80
"""Longest line, in characters, still taken for a heading."""

H1_RATIO = 1.6
"""Font size, relative to the body text, from which a line is an ``<h1>``."""
H2_RATIO = 1.25
"""Font size, relative to the body text, from which a line is an ``<h2>``."""

_ROMAN = r"(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_EN_NUMBERS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    "last|final"
)
_PL_NUMBERS = (
    "(?:pierwsz|drug|trzec|czwart|piat|szost|siodm|osm|dziewiat|dziesiat|"
    "jedenast|dwunast|trzynast|czternast|pietnast|szesnast|siedemnast|osiemnast|"
    "dziewietnast|dwudziest|ostatn)(?:y|a|e|i)"
)
_NUMBER = rf"(?:\d{{1,3}}|{_ROMAN}|{_EN_NUMBERS}|{_PL_NUMBERS})"
_NUMBERED = "chapter|part|book|volume|act|rozdzial|czesc|ksiega|tom|akt"
_STANDALONE = (
    "prologue|prolog|epilogue|epilog|interlude|intermezzo|introduction|preface|"
    "foreword|afterword|wstep|przedmowa|przedslowie|poslowie|wprowadzenie|"
    "zakonczenie"
)
_CHAPTER = re.compile(rf"^(?:{_NUMBERED})\s+{_NUMBER}\b(?P<rest>.*)$")
_STANDALONE_TITLE = re.compile(rf"^(?:{_STANDALONE})(?P<rest>(?:\s*[.:\-–—]\s*.*)?)$")
_SENTENCE_END = re.compile(r"[.,;!?…]$")
_BARE_NUMBER = re.compile(r"^(?:\d{1,3}|[IVXLCDM]{1,7})\.?$")
_NOT_A_TITLE = re.compile(r"[\"“”„«»'’]|^[-–—]|[.,;!?…]$")
_CSS_RULE = re.compile(r"([^{}]+)\{([^}]*)\}")
_CSS_CLASS = re.compile(r"\.([\w-]+)\s*$")
_CSS_SIZE = re.compile(
    r"font(?:-size)?\s*:[^;]*?(\d+(?:\.\d+)?)(px|pt)\b", re.IGNORECASE
)
_PT_TO_PX = 4 / 3


def is_heading_text(text: str) -> bool:
    """Return True if a line of text reads like a chapter or section title.

    Recognised are numbered chapters and parts (``Chapter 3``, ``Part Two:
    The Return``, ``Rozdział pierwszy``, ``IV``), unnumbered parts of the
    main text (``Prologue``, ``Epilog``) and whole titles of front and back
    matter (``Acknowledgments``, ``Spis treści``), in English and Polish.
    """
    text = " ".join(text.split())
    if not text or len(text) > MAX_HEADING_LENGTH:
        return False
    if _BARE_NUMBER.match(text):
        return True
    folded = fold(text)
    if match := _CHAPTER.match(folded) or _STANDALONE_TITLE.match(folded):
        # "Chapter 1." and "Part 2: The Return" are titles; "Part 2 of the
        # plan was simple." is a sentence.
        rest = match["rest"].strip()
        return rest in ("", ".") or not _SENTENCE_END.search(rest)
    return not _NOT_A_TITLE.search(text) and normalize(text) in TITLE_PHRASES


def class_font_sizes(soup: BeautifulSoup) -> dict[str, float]:
    """Read the font size each CSS class sets in the document's ``<style>``.

    Sizes are in pixels; ``pt`` values are converted. Word processors that
    export HTML (TextEdit, Pages, Google Docs) show headings this way.
    """
    sizes: dict[str, float] = {}
    for style in soup.find_all("style"):
        for selectors, declarations in _CSS_RULE.findall(style.get_text()):
            size = _CSS_SIZE.search(declarations)
            if size is None:
                continue
            pixels = float(size[1]) * (_PT_TO_PX if size[2].lower() == "pt" else 1)
            for selector in selectors.split(","):
                if match := _CSS_CLASS.search(selector.strip()):
                    sizes[match[1]] = pixels
    return sizes


def has_headings(root: Tag) -> bool:
    """Return True if ``root`` holds an ``<h1>``–``<h3>`` with text."""
    return any(
        isinstance(heading, Tag) and text_length(heading)
        for heading in root.find_all(["h1", "h2", "h3"])
    )


def promote_headings(root: Tag, class_sizes: Mapping[str, float] | None = None) -> int:
    """Turn paragraphs that look like headings into ``<h1>``/``<h2>``, in place.

    A paragraph becomes a heading when its text reads like a title (see
    :func:`is_heading_text`) or when its CSS class sets a font clearly
    bigger than the body text's.

    Args:
        root: The document body.
        class_sizes: Font sizes by CSS class, see :func:`class_font_sizes`.

    Returns:
        How many paragraphs were promoted.
    """
    paragraphs = [
        tag
        for tag in root.find_all(["p", "div"])
        if isinstance(tag, Tag) and not tag.find(BLOCK_TAGS)
    ]
    sizes = {id(tag): _class_size(tag, class_sizes or {}) for tag in paragraphs}
    body_size = _body_size(paragraphs, sizes)
    promoted = 0
    for tag in paragraphs:
        text = single_line(tag)
        if not text or len(text) > MAX_HEADING_LENGTH:
            continue
        size = sizes[id(tag)]
        if body_size and size and size >= body_size * H1_RATIO:
            tag.name = "h1"
        elif body_size and size and size >= body_size * H2_RATIO:
            tag.name = "h2"
        elif is_heading_text(text):
            tag.name = "h1"
        else:
            continue
        promoted += 1
    return promoted


def _class_size(tag: Tag, class_sizes: Mapping[str, float]) -> float | None:
    """Return the font size a paragraph's CSS classes give it, if any."""
    found = [class_sizes[name] for name in class_names(tag) if name in class_sizes]
    return max(found) if found else None


def _body_size(
    paragraphs: list[Tag], sizes: Mapping[int, float | None]
) -> float | None:
    """Return the font size of most of the text, weighted by characters."""
    weights: Counter[float] = Counter()
    for tag in paragraphs:
        if (size := sizes[id(tag)]) is not None:
            weights[size] += text_length(tag)
    return weights.most_common(1)[0][0] if weights else None
