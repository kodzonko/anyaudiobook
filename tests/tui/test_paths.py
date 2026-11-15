"""Tests for reading pasted and dropped paths."""

from pathlib import Path

import pytest

from anyaudiobook.tui.paths import parse_path_input


@pytest.fixture
def spaced(tmp_path: Path) -> Path:
    """An existing file with spaces and an apostrophe in its path."""
    folder = tmp_path / "My Books"
    folder.mkdir()
    path = folder / "Jane's book.epub"
    path.write_text("")
    return path


@pytest.mark.parametrize(
    "shape",
    [
        "{path}",
        "  {path}  \n",
        '"{path}"',
        "{escaped}",
        "file://{url}",
    ],
    ids=["plain", "padded", "double-quoted", "escaped", "file-url"],
)
def test_parse_path_input_reads_terminal_shapes(spaced: Path, shape: str) -> None:
    escaped = str(spaced).replace(" ", "\\ ").replace("'", "\\'")
    url = str(spaced).replace(" ", "%20")

    text = shape.format(path=spaced, escaped=escaped, url=url)

    assert parse_path_input(text) == spaced


def test_parse_path_input_handles_single_quotes(tmp_path: Path) -> None:
    path = tmp_path / "My Books.epub"
    path.write_text("")

    assert parse_path_input(f"'{path}'") == path


def test_parse_path_input_expands_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert parse_path_input("~/missing.epub") == tmp_path / "missing.epub"


@pytest.mark.parametrize("text", ["", "   "])
def test_parse_path_input_ignores_blanks(text: str) -> None:
    assert parse_path_input(text) is None


def test_parse_path_input_returns_the_unwrapped_missing_path() -> None:
    assert parse_path_input("'/nowhere/a book.epub'") == Path("/nowhere/a book.epub")
    assert parse_path_input("/nowhere/'unbalanced.epub") == Path(
        "/nowhere/'unbalanced.epub"
    )
