"""Rejoin text that was broken into lines for print, shared by TXT and PDF."""

import re
from collections.abc import Iterable

_HYPHENATED = re.compile(r"\w[-­]$")
_SOFT_HYPHEN = "­"


def join_lines(lines: Iterable[str]) -> str:
    """Join wrapped lines into one paragraph.

    Lines are joined with a space, except that a word hyphenated at the end
    of a line (``foolish-`` + ``ness``) is joined back together. Soft
    hyphens are dropped.

    Args:
        lines: The lines of one paragraph, in order.

    Returns:
        The paragraph on one line.
    """
    text = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not text:
            text = line
        elif _HYPHENATED.search(text) and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}"
    return text.replace(_SOFT_HYPHEN, "")
