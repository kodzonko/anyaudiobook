"""Read a path the way people paste it into a terminal."""

import os
import shlex
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname


def parse_path_input(text: str) -> Path | None:
    """Turn a typed, pasted or dropped path into a :class:`Path`.

    Terminals hand over dropped files in different shapes: quoted
    (``'/My Books/a.epub'``), with escaped spaces (``/My\\ Books/a.epub``)
    or as a ``file://`` URL. Each reading is tried and the first that
    exists wins; if none exists, the most unwrapped reading is returned so
    the user sees what is missing. ``~`` is expanded.

    Args:
        text: What the user entered.

    Returns:
        The path, or None when ``text`` is blank.
    """
    text = text.strip()
    if not text:
        return None
    if text.startswith("file://"):
        text = url2pathname(unquote(urlparse(text).path))
    readings = [text]
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        readings.append(text[1:-1])
    if os.name != "nt":  # backslashes separate Windows paths; never unescape
        try:
            words = shlex.split(text)
        except ValueError:  # unbalanced quotes
            words = []
        if len(words) == 1:
            readings.append(words[0])
    paths = [Path(reading).expanduser() for reading in readings]
    return next((path for path in paths if path.exists()), paths[-1])
