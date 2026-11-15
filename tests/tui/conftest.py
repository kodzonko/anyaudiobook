"""Fixtures for driving the TUI: a test app, a book, voices and a store."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from textual import events
from textual.pilot import Pilot
from textual.widgets import Input

from anyaudiobook.store import Store
from anyaudiobook.tui import AnyAudiobookApp, TuiConfig
from anyaudiobook.voices import Voice
from tests.builders import Para, write_docx
from tests.fake_worker import COMMAND
from tests.test_voices import AVA, RYAN, ZOFIA

VOICES = [AVA, RYAN, ZOFIA]
LONG = " ".join(["The story goes on."] * 60)
SIZE = (110, 50)
"""Terminal size for the tests: tall enough to show the whole form."""


class RecordingApp(AnyAudiobookApp):
    """The app, keeping the messages of its notifications for tests."""

    def __init__(self, config: TuiConfig) -> None:
        """Start with no notifications."""
        super().__init__(config)
        self.notes: list[str] = []

    def notify(self, message: str, **kwargs: Any) -> None:
        """Record the notification, then show it."""
        self.notes.append(message)
        super().notify(message, **kwargs)


AppFactory = Callable[..., RecordingApp]


async def fetch_test_voices() -> list[Voice]:
    """Stand in for the download of the voices."""
    return list(VOICES)


async def fetch_offline() -> list[Voice]:
    """Fail like a download without internet."""
    raise OSError("Network is unreachable")


@pytest.fixture
def store(tmp_path: Path) -> Store:
    """An empty store in the test's app folder."""
    return Store.in_folder(tmp_path / "app")


@pytest.fixture
def make_app(store: Store) -> AppFactory:
    """Return a factory of apps using ``store``, the test voices and the fake worker."""

    def factory(**changes: Any) -> RecordingApp:
        settings: dict[str, Any] = {
            "store": store,
            "fetch_voices": fetch_test_voices,
            "worker_command": COMMAND,
        }
        return RecordingApp(TuiConfig(**(settings | changes)))

    return factory


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """A two-chapter DOCX called Lorem Ipsum, by Jane Doe."""
    folder = tmp_path / "books"
    folder.mkdir()
    return write_docx(
        folder / "lorem.docx",
        [
            Para("Chapter 1", "Heading1"),
            Para(LONG),
            Para("Chapter 2", "Heading1"),
            Para(LONG),
        ],
        title="Lorem Ipsum",
        author="Jane Doe",
    )


async def wait_for(
    pilot: Pilot[Any], condition: Callable[[], object], timeout: float = 60
) -> None:
    """Let the app run until ``condition()`` holds."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError("the app never got there")
        await pilot.pause(0.02)


async def paste(pilot: Pilot[Any], selector: str, text: str) -> None:
    """Paste ``text`` into the input at ``selector``, like a terminal does."""
    field = pilot.app.screen.query_one(selector, Input)
    field.focus()
    field.post_message(events.Paste(text))
    await pilot.pause()
