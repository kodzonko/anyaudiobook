"""Tests for keyword normalisation and the keyword tables."""

import pytest

from anyaudiobook.matter.keywords import (
    FILE_NAME_WORDS,
    TITLE_PHRASES,
    fold,
    normalize,
)
from anyaudiobook.matter.models import MatterKind


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Źródła", "zrodla"),
        ("Podziękowania", "podziekowania"),
        ("Łódź", "lodz"),
        ("ACKNOWLEDGEMENTS", "acknowledgements"),
    ],
)
def test_fold_strips_diacritics_and_case(text: str, expected: str) -> None:
    assert fold(text) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Spis treści:", "spis tresci"),
        ("7. Podziękowania", "podziekowania"),
        ("  Publisher’s   Note ", "publisher s note"),
        ("O_autorze", "o autorze"),
        ("1984", "1984"),
    ],
)
def test_normalize(title: str, expected: str) -> None:
    assert normalize(title) == expected


def test_title_phrases_are_stored_normalized() -> None:
    assert TITLE_PHRASES["spis tresci"] is MatterKind.TOC
    assert TITLE_PHRASES["publisher s note"] is MatterKind.EDITORIAL_NOTE
    assert all(phrase == normalize(phrase) for phrase in TITLE_PHRASES)


def test_file_name_words_are_folded_letters() -> None:
    assert all(word.isalpha() and word == fold(word) for word in FILE_NAME_WORDS)
    assert "index" not in FILE_NAME_WORDS
