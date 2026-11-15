"""End-to-end tests of the voice preview.

A stand-in engine "narrates" by writing the text itself, and small Python
scripts stand in for the audio player.
"""

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from anyaudiobook.prosody import Prosody
from anyaudiobook.tts import TextProgress
from anyaudiobook.tui.form import TUNING_HINT, FormScreen, opening
from anyaudiobook.tui.widgets import ChoiceList, Slider
from anyaudiobook.voices import VoiceFetcher
from tests.tui.conftest import (
    SIZE,
    AppFactory,
    RecordingApp,
    fetch_offline,
    fetch_test_voices,
    paste,
    wait_for,
)

COPY = "import shutil, sys; shutil.copy(sys.argv[2], sys.argv[1])"
"""Plays by copying the audio to the path given first."""
FAIL = "import sys; sys.exit('no audio device')"
WAIT = (
    "import os, sys, time;"
    " open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(60)"
)
"""Plays for a minute, after writing its process id to the path given first."""


@dataclass(frozen=True)
class TextEngine:
    """Narrates by writing the text itself."""

    voice: str
    prosody: Prosody
    audio_suffix: ClassVar[str] = ".mp3"

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Write ``text`` as the "audio"."""
        output_path.write_text(text, encoding="utf-8")


def player(script: str, *args: str) -> Callable[[], list[str]]:
    """A player running ``script`` with ``args``, then the audio file."""
    return lambda: [sys.executable, "-c", script, *args]


def tuning_note(app: RecordingApp) -> str:
    """The note under the sliders, where the preview says how it goes."""
    return str(app.screen.query_one("#tuning-note", Static).render())


async def ready(pilot: Pilot[Any], app: RecordingApp, book: Path | None) -> FormScreen:
    """Fill in the ebook, if any, and wait until the voices are known."""
    screen = app.screen
    assert isinstance(screen, FormScreen)
    status = screen.query_one("#voices-status", Static)
    await wait_for(pilot, lambda: "voices" in str(status.render()))
    if book is not None:
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
    return screen


@pytest.mark.anyio
async def test_the_preview_reads_the_opening_with_the_tuned_voice(
    make_app: AppFactory, book: Path, tmp_path: Path
) -> None:
    played = tmp_path / "played.mp3"
    engines: list[TextEngine] = []

    def engine(voice: str, prosody: Prosody) -> TextEngine:
        engines.append(TextEngine(voice, prosody))
        return engines[-1]

    app = make_app(preview_engine=engine, find_player=player(COPY, str(played)))
    async with app.run_test(size=SIZE) as pilot:
        screen = await ready(pilot, app, book)
        screen.query_one("#rate", Slider).focus()
        await pilot.press("right", "enter", "left")  # speed +5%, pitch -5Hz

        await pilot.press("ctrl+t")
        await wait_for(pilot, played.exists)
        await wait_for(pilot, lambda: tuning_note(app) == TUNING_HINT)

        voice = screen.query_one("#voice", ChoiceList).value
        assert voice is not None
        assert engines == [TextEngine(voice, Prosody(rate=5, pitch=-5))]
        assert played.read_text(encoding="utf-8") == (
            "Chapter 1" + " The story goes on." * 10
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("with_book", "fetch", "message"),
    [
        (False, fetch_test_voices, "Choose an ebook first"),
        (True, fetch_offline, "Choose a voice first"),
        (True, fetch_test_voices, "Previews need an audio player"),
    ],
    ids=["no ebook", "no voice", "no player"],
)
async def test_the_preview_says_what_it_needs(
    make_app: AppFactory,
    book: Path,
    with_book: bool,
    fetch: VoiceFetcher,
    message: str,
) -> None:
    app = make_app(fetch_voices=fetch, find_player=lambda: None)
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot, app, book if with_book else None)

        await pilot.press("ctrl+t")

        assert app.notes[-1].startswith(message)


@pytest.mark.anyio
async def test_a_failing_player_is_reported(make_app: AppFactory, book: Path) -> None:
    app = make_app(preview_engine=TextEngine, find_player=player(FAIL))
    async with app.run_test(size=SIZE) as pilot:
        screen = await ready(pilot, app, book)

        await pilot.click("#preview")
        note = screen.query_one("#tuning-note", Static)
        await wait_for(pilot, lambda: note.has_class("-error"))

        assert "Cannot preview: the player (python" in tuning_note(app)
        assert "no audio device" in tuning_note(app)


@pytest.mark.anyio
async def test_escape_stops_the_preview_and_its_player(
    make_app: AppFactory, book: Path, tmp_path: Path
) -> None:
    pid_file = tmp_path / "player.pid"
    app = make_app(preview_engine=TextEngine, find_player=player(WAIT, str(pid_file)))
    async with app.run_test(size=SIZE) as pilot:
        await ready(pilot, app, book)
        await pilot.press("ctrl+t")
        await wait_for(pilot, lambda: pid_file.exists() and pid_file.read_text())
        assert "Playing a sample" in tuning_note(app)

        await pilot.press("escape")
        pid = int(pid_file.read_text())
        await wait_for(pilot, lambda: not running(pid), timeout=10)

        assert tuning_note(app) == TUNING_HINT


def running(pid: int) -> bool:
    """Whether the process ``pid`` is still there."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  One\n two. ", "One two."),
        ("One two. Three four five six seven.", "One two."),
        ("Onetwothree fourfive sixseven", "Onetwothree fourfive…"),
        ("Hi. Onetwothree fourfives sixseven", "Hi. Onetwothree…"),
    ],
    ids=["short", "whole sentences", "between words", "sentence too short"],
)
def test_opening_cuts_the_sample_at_a_sentence_or_word(
    text: str, expected: str
) -> None:
    assert opening(text, limit=20) == expected
