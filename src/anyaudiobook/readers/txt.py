"""Read plain text books."""

import re
import statistics
from collections.abc import Iterator
from html import escape
from pathlib import Path

import charset_normalizer

from anyaudiobook.readers.base import HtmlBookReader, HtmlSource
from anyaudiobook.readers.headings import is_heading_text
from anyaudiobook.readers.lines import join_lines

LONG_LINE = 100
"""Median line length from which every line is taken for a paragraph of its
own, rather than for a line wrapped at a fixed width."""

_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_INDENT = re.compile(r"^(?:\t| {2,})\S")
_GUTENBERG = re.compile(
    r"^\*{3}\s*(?P<edge>START|END) OF (?:THE|THIS) PROJECT GUTENBERG.*$",
    re.IGNORECASE | re.MULTILINE,
)


class TextReader(HtmlBookReader):
    """Reads plain text in any common encoding (UTF-8, CP1250, ISO-8859-2...).

    Paragraphs are separated by blank lines or indentation; lines wrapped at
    a fixed width are joined back. Chapters are found by their titles
    (``Chapter 3``, ``Rozdział III``, ``Epilogue``...), see
    :mod:`anyaudiobook.readers.headings`. Project Gutenberg's licence header
    and footer are left out.
    """

    suffixes = (".txt", ".text")

    def load(self, path: Path) -> HtmlSource:
        """Turn the text into HTML paragraphs."""
        text = strip_gutenberg(decode_text(path.read_bytes()))
        body = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs(text))
        return HtmlSource(f"<html><body>{body}</body></html>")


def decode_text(data: bytes) -> str:
    """Decode text of an unknown encoding, trying UTF-8 first."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        best = charset_normalizer.from_bytes(data).best()
        text = str(best) if best is not None else data.decode("utf-8", "replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_gutenberg(text: str) -> str:
    """Keep only the book between Project Gutenberg's START and END lines."""
    for match in _GUTENBERG.finditer(text):
        if match["edge"].upper() == "START":
            text = text[match.end() :]
            return strip_gutenberg(text)
        return text[: match.start()]
    return text


def paragraphs(text: str) -> Iterator[str]:
    """Yield the paragraphs of a plain text, each on one line.

    A chapter title on the first line of a block gets a paragraph of its
    own, so it can be recognised as a heading.
    """
    for block in _BLANK_LINE.split(text):
        lines = [line for line in block.split("\n") if line.strip()]
        if lines and len(lines) > 1 and is_heading_text(lines[0]):
            yield " ".join(lines.pop(0).split())
        if not lines:
            continue
        if statistics.median(len(line) for line in lines) >= LONG_LINE:
            yield from (" ".join(line.split()) for line in lines)
            continue
        paragraph: list[str] = []
        for line in lines:
            if paragraph and _INDENT.match(line):
                yield join_lines(paragraph)
                paragraph = []
            paragraph.append(line)
        yield join_lines(paragraph)
