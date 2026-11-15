"""How far a conversion has got, reported as events.

A conversion tells a :data:`ProgressCallback` what it is doing. The events
are pydantic models so the worker process (:mod:`anyaudiobook.worker`) can
stream them to the TUI as JSON lines (:func:`dump_event`,
:func:`load_event`), and :func:`describe` turns them into log lines.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class _Event(BaseModel):
    """Base of the progress events: immutable, tagged by ``kind``."""

    model_config = ConfigDict(frozen=True)


class Reading(_Event):
    """The ebook is being read and split into chapters."""

    kind: Literal["reading"] = "reading"


class NarrationStarted(_Event):
    """Narration begins: how much there is to narrate."""

    kind: Literal["narration_started"] = "narration_started"
    chapters: int
    characters: int
    """Characters of text in all chapters together."""


class ChapterStarted(_Event):
    """A chapter's narration begins."""

    kind: Literal["chapter_started"] = "chapter_started"
    position: int
    """1-based position among the chapters being narrated."""
    total: int
    title: str


class ChapterNarrated(_Event):
    """A chapter's audio file is complete."""

    kind: Literal["chapter_narrated"] = "chapter_narrated"
    position: int
    total: int
    title: str
    path: Path


class Advanced(_Event):
    """More text was narrated; sent often, so it is not logged."""

    kind: Literal["advanced"] = "advanced"
    characters: int
    """Characters narrated so far, across all chapters."""


class Packaging(_Event):
    """The narrated chapters are being packaged (tagged, or joined)."""

    kind: Literal["packaging"] = "packaging"
    output_format: str


class Finished(_Event):
    """The audiobook is written."""

    kind: Literal["finished"] = "finished"
    paths: tuple[Path, ...]


class Failed(_Event):
    """The conversion stopped with an error."""

    kind: Literal["failed"] = "failed"
    message: str


ProgressEvent = (
    Reading
    | NarrationStarted
    | ChapterStarted
    | ChapterNarrated
    | Advanced
    | Packaging
    | Finished
    | Failed
)
"""Any of the events a conversion reports."""

ProgressCallback = Callable[[ProgressEvent], None]
"""Receives the events of a conversion, in order."""

_ADAPTER: TypeAdapter[ProgressEvent] = TypeAdapter(
    Annotated[ProgressEvent, Field(discriminator="kind")]
)


def ignore(event: ProgressEvent) -> None:
    """A :data:`ProgressCallback` that does nothing."""


def dump_event(event: ProgressEvent) -> str:
    """Serialise an event as one line of JSON."""
    return _ADAPTER.dump_json(event).decode()


def load_event(line: str | bytes) -> ProgressEvent:
    """Parse a line written by :func:`dump_event`.

    Raises:
        pydantic.ValidationError: If the line is not an event.
    """
    return _ADAPTER.validate_json(line)


def describe(event: ProgressEvent) -> str | None:
    """Return a log line for ``event``, or None for the frequent :class:`Advanced`."""
    match event:
        case Reading():
            return "Reading the ebook"
        case NarrationStarted(chapters=chapters, characters=characters):
            return f"Narrating {chapters} chapters ({characters:,} characters)"
        case ChapterStarted(position=position, total=total, title=title):
            return f"Narrating {position}/{total}: {title}"
        case ChapterNarrated(position=position, total=total, title=title, path=path):
            return f"Narrated {position}/{total}: {title} -> {path.name}"
        case Packaging(output_format=output_format):
            return f"Packaging the {output_format.upper()} audiobook"
        case Finished(paths=paths):
            return f"Done: wrote {_files(paths)}"
        case Failed(message=message):
            return f"Failed: {message}"
        case Advanced():
            return None


def _files(paths: tuple[Path, ...]) -> str:
    """Name what was written: one file, or how many files in which folder."""
    if len(paths) == 1:
        return str(paths[0])
    folder = paths[0].parent if paths else Path()
    return f"{len(paths)} files in {folder}"
