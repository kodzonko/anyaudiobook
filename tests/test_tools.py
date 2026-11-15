"""Tests for finding external programs."""

import shutil

import pytest

from anyaudiobook.tools import find_player


@pytest.mark.parametrize(
    ("installed", "expected"),
    [
        ({"afplay", "ffplay", "mpv"}, ["/bin/afplay"]),
        (
            {"ffplay", "mpv"},
            ["/bin/ffplay", "-nodisp", "-autoexit", "-loglevel", "error"],
        ),
        ({"mpv", "mpg123"}, ["/bin/mpv", "--no-video", "--no-terminal"]),
        ({"mpg123"}, ["/bin/mpg123", "-q"]),
        (set(), None),
    ],
    ids=["macOS", "ffmpeg", "mpv", "mpg123", "none"],
)
def test_find_player_prefers_the_players_in_order(
    monkeypatch: pytest.MonkeyPatch, installed: set[str], expected: list[str] | None
) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda name: f"/bin/{name}" if name in installed else None
    )

    assert find_player() == expected
