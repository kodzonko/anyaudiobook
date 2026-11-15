"""End-to-end tests of the TUI: a real app, worker process and store.

Only the download of the voices and the speech engine are replaced; the
conversion runs in a worker process like it does for users.
"""

import sys
from pathlib import Path

import pytest
from mutagen.mp4 import MP4
from textual.widgets import Input, Static

from anyaudiobook.store import Choices, Store
from anyaudiobook.tui import Detached
from anyaudiobook.tui.conversion import ConversionScreen
from anyaudiobook.tui.form import FormScreen, ReportScreen
from anyaudiobook.tui.widgets import ChoiceList
from tests.test_voices import AVA, RYAN, ZOFIA
from tests.tui.conftest import (
    SIZE,
    AppFactory,
    RecordingApp,
    fetch_offline,
    paste,
    wait_for,
)

pytestmark = pytest.mark.anyio


def form(app: RecordingApp) -> FormScreen:
    """The app's form screen."""
    screen = app.screen
    assert isinstance(screen, FormScreen)
    return screen


def note(screen: FormScreen, selector: str) -> str:
    """The text of a note on the form."""
    return str(screen.query_one(selector, Static).render())


async def test_converting_a_book_to_mp3_with_a_log(
    make_app: AppFactory, book: Path, store: Store
) -> None:
    app = make_app(log=True)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)

        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        output = book.parent / "Jane Doe - Lorem Ipsum"
        assert screen.query_one("#output", Input).value == str(output)
        assert "2 chapters to narrate" in note(screen, "#book")
        assert "Lorem Ipsum.log" in note(screen, "#output-note")

        screen.query_one("#language", ChoiceList).focus()
        await pilot.press("p", "enter")  # Polish
        assert screen.query_one("#voice", ChoiceList).value == ZOFIA.short_name
        await pilot.press("enter")  # the only Polish voice, then Convert
        await pilot.press("enter")

        assert isinstance(app.screen, ConversionScreen)
        conversion = app.screen
        await wait_for(pilot, lambda: conversion.ended)

        assert conversion.error is None
        assert str(conversion.query_one("#status", Static).render()).startswith(
            "✓ Done"
        )
        frame = conversion.query_one("#progress").region
        bar = conversion.query_one("#progress Bar").region
        assert bar.y == frame.y and bar.width > SIZE[0] // 2  # visible and wide
        assert sorted(p.name for p in output.iterdir()) == [
            "1. Chapter 1.mp3",
            "2. Chapter 2.mp3",
            "Jane Doe - Lorem Ipsum.log",
        ]
        log = (output / "Jane Doe - Lorem Ipsum.log").read_text(encoding="utf-8")
        assert ZOFIA.short_name in log

        await pilot.press("n")  # back to the form for another book
        assert isinstance(app.screen, FormScreen)

    assert store.load_choices() == Choices("mp3", "pl", {"pl": ZOFIA.short_name})


async def test_converting_a_book_to_m4b(
    make_app: AppFactory, book: Path, ffmpeg: str
) -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)

        screen.query_one("#format", ChoiceList).focus()
        await pilot.press("down", "space")
        output = book.parent / "Jane Doe - Lorem Ipsum.m4b"
        assert screen.query_one("#output", Input).value == str(output)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)
        await pilot.press("ctrl+s")

        conversion = app.screen
        assert isinstance(conversion, ConversionScreen)
        await wait_for(pilot, lambda: conversion.ended)

    assert conversion.paths == (str(output),)
    tags = MP4(output).tags
    assert tags is not None and tags["\xa9nam"] == ["Lorem Ipsum"]


async def test_detach_starts_the_conversion_and_exits(
    make_app: AppFactory, book: Path
) -> None:
    app = make_app(detach=True, log=True)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)
        await pilot.press("ctrl+s")
        await wait_for(pilot, lambda: app.return_value is not None)

    result = app.return_value
    assert isinstance(result, Detached)
    assert result.process.wait(timeout=60) == 0
    output = book.parent / "Jane Doe - Lorem Ipsum"
    assert (output / "2. Chapter 2.mp3").exists()
    assert "Done: wrote 2 files" in result.job.log_path.read_text(encoding="utf-8")


async def test_a_detached_worker_that_cannot_start_is_reported(
    make_app: AppFactory, book: Path, tmp_path: Path
) -> None:
    app = make_app(detach=True, worker_command=(str(tmp_path / "no-such-program"),))
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)
        await pilot.press("ctrl+s")

        assert app.return_value is None
        assert "no-such-program" in app.notes[-1]


async def test_the_last_choices_are_chosen_again(
    make_app: AppFactory, store: Store
) -> None:
    store.save_choices("mp3", "en", AVA.short_name)
    store.save_choices("m4b", "pl", ZOFIA.short_name)
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)

        assert screen.query_one("#format", ChoiceList).value == "m4b"
        assert screen.query_one("#language", ChoiceList).value == "pl"
        assert screen.query_one("#voice", ChoiceList).value == ZOFIA.short_name

        screen.query_one("#language", ChoiceList).focus()
        await pilot.press("e", "enter")

        assert screen.query_one("#voice", ChoiceList).value == AVA.short_name


async def test_saved_voices_are_used_when_offline(
    make_app: AppFactory, store: Store
) -> None:
    store.save_voices([RYAN, ZOFIA])
    app = make_app(fetch_voices=fetch_offline)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await wait_for(pilot, lambda: "saved list" in note(screen, "#voices-status"))

        assert screen.query_one("#voice", ChoiceList).value == RYAN.short_name
        assert "Network is unreachable" in note(screen, "#voices-status")


async def test_without_voices_the_form_says_what_is_missing(
    make_app: AppFactory, store: Store
) -> None:
    app = make_app(fetch_voices=fetch_offline)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await wait_for(
            pilot, lambda: "Could not download" in note(screen, "#voices-status")
        )

        await pilot.press("ctrl+s")

        assert isinstance(app.screen, FormScreen)
        assert app.notes == [
            (
                "Choose an ebook to convert.\n"
                "Choose where to save the audiobook.\n"
                "Choose a voice; the list of voices has not loaded."
            )
        ]
    assert store.voices() == []


async def test_downloaded_voices_are_saved(make_app: AppFactory, store: Store) -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await wait_for(pilot, lambda: "up to date" in note(screen, "#voices-status"))

    assert store.voices() == sorted([AVA, RYAN, ZOFIA], key=lambda v: v.short_name)


async def test_an_edited_output_keeps_its_place_when_the_format_changes(
    make_app: AppFactory, book: Path, tmp_path: Path
) -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        output = screen.query_one("#output", Input)
        output.value = str(tmp_path / "Custom Name")

        screen.query_one("#format", ChoiceList).focus()
        await pilot.press("down", "enter")
        as_m4b = output.value
        await pilot.press("shift+tab", "up", "enter")

        assert as_m4b == str(tmp_path / "Custom Name.m4b")
        assert output.value == str(tmp_path / "Custom Name")


async def test_the_form_warns_before_replacing_a_file(
    make_app: AppFactory, book: Path
) -> None:
    (book.parent / "Jane Doe - Lorem Ipsum.m4b").write_bytes(b"old")
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        screen.query_one("#format", ChoiceList).choose("m4b")
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)

        assert "will be replaced" in note(screen, "#output-note")


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("notes.xyz", "hello", "Cannot read .xyz files"),
        ("broken.epub", "not a zip", "Cannot read this ebook"),
        (None, None, "No file at"),
    ],
    ids=["unsupported", "broken", "missing"],
)
async def test_the_form_explains_unusable_files(
    make_app: AppFactory,
    tmp_path: Path,
    name: str | None,
    content: str | None,
    message: str,
) -> None:
    path = tmp_path / (name or "missing.epub")
    if content is not None:
        path.write_text(content)
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(path))
        await wait_for(pilot, lambda: message in note(screen, "#book"))

        assert screen.preview is None
        await pilot.press("ctrl+r")
        assert app.notes == ["Choose an ebook first."]


async def test_the_report_shows_what_is_narrated(
    make_app: AppFactory, book: Path
) -> None:
    app = make_app()
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)

        await pilot.press("ctrl+r")
        assert isinstance(app.screen, ReportScreen)
        assert "Chapter 1" in app.screen.preview.report
        await pilot.press("escape")

        assert app.screen is screen


async def test_quitting_twice_stops_a_running_conversion(
    make_app: AppFactory, book: Path
) -> None:
    sleeper = (sys.executable, "-c", "import time; time.sleep(60)")
    app = make_app(worker_command=sleeper)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)
        await pilot.press("ctrl+s")
        conversion = app.screen
        assert isinstance(conversion, ConversionScreen)
        await wait_for(pilot, lambda: conversion.process)

        await pilot.press("q")
        assert conversion.running
        assert "Press q again" in app.notes[-1]
        await pilot.press("q")

    assert conversion.process is not None
    assert conversion.process.returncode is not None


async def test_a_failing_worker_is_reported(make_app: AppFactory, book: Path) -> None:
    crasher = (sys.executable, "-c", "import sys; sys.exit('worker exploded')")
    app = make_app(worker_command=crasher)
    async with app.run_test(size=SIZE) as pilot:
        screen = form(app)
        await paste(pilot, "#source", str(book))
        await wait_for(pilot, lambda: screen.preview)
        await wait_for(pilot, lambda: screen.query_one("#voice", ChoiceList).value)
        await pilot.press("ctrl+s")
        conversion = app.screen
        assert isinstance(conversion, ConversionScreen)
        await wait_for(pilot, lambda: conversion.ended)

        status = str(conversion.query_one("#status", Static).render())
        assert status.startswith("✗ Conversion failed")
        assert "worker exploded" in status
        await pilot.press("q")  # quits at once once nothing runs
