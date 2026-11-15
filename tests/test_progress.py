"""Tests for progress events: their JSON lines and log lines."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from anyaudiobook.progress import (
    Advanced,
    ChapterNarrated,
    ChapterStarted,
    Failed,
    Finished,
    NarrationStarted,
    Packaging,
    ProgressEvent,
    Reading,
    describe,
    dump_event,
    load_event,
)

EVENTS: list[ProgressEvent] = [
    Reading(),
    NarrationStarted(chapters=3, characters=12000),
    ChapterStarted(position=1, total=3, title="Chapter 1"),
    ChapterNarrated(position=1, total=3, title="Chapter 1", path=Path("/a/1.mp3")),
    Advanced(characters=500),
    Packaging(output_format="m4b"),
    Finished(paths=(Path("/a/Book.m4b"),)),
    Failed(message="ffmpeg is not installed"),
]


@pytest.mark.parametrize("event", EVENTS, ids=lambda event: event.kind)
def test_events_survive_a_json_line(event: ProgressEvent) -> None:
    line = dump_event(event)

    assert "\n" not in line
    assert load_event(line) == event


def test_load_event_rejects_other_output() -> None:
    with pytest.raises(ValidationError):
        load_event("Unpacking Book...")


@pytest.mark.parametrize(
    ("event", "line"),
    [
        (Reading(), "Reading the ebook"),
        (
            NarrationStarted(chapters=3, characters=12000),
            "Narrating 3 chapters (12,000 characters)",
        ),
        (ChapterStarted(position=2, total=3, title="Two"), "Narrating 2/3: Two"),
        (
            ChapterNarrated(position=2, total=3, title="Two", path=Path("/a/2.mp3")),
            "Narrated 2/3: Two -> 2.mp3",
        ),
        (Packaging(output_format="m4b"), "Packaging the M4B audiobook"),
        (Finished(paths=(Path("/a/B.m4b"),)), f"Done: wrote {Path('/a/B.m4b')}"),
        (
            Finished(paths=(Path("/a/1.mp3"), Path("/a/2.mp3"))),
            f"Done: wrote 2 files in {Path('/a')}",
        ),
        (Failed(message="boom"), "Failed: boom"),
        (Advanced(characters=10), None),
    ],
)
def test_describe_gives_log_lines(event: ProgressEvent, line: str | None) -> None:
    assert describe(event) == line
