"""Tests for rejoining lines wrapped for print."""

import pytest

from anyaudiobook.readers.lines import join_lines


@pytest.mark.parametrize(
    ("lines", "text"),
    [
        (["one two", "three"], "one two three"),
        (["foolish-", "ness"], "foolishness"),
        (["self-", "Aware"], "self- Aware"),
        (["soft­", "hyphen in­side"], "softhyphen inside"),
        (["  padded  ", "", " lines "], "padded lines"),
        (["- dash", "x"], "- dash x"),
        ([], ""),
    ],
)
def test_join_lines(lines: list[str], text: str) -> None:
    assert join_lines(lines) == text
