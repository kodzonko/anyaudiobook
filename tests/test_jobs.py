"""Tests for conversion jobs: output paths, running, logging and detaching."""

import os
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from anyaudiobook.jobs import (
    WORKER_COMMAND,
    AdvancedSettings,
    ConversionJob,
    default_output,
    job_log,
    log_path,
    resolve_output,
    run_job,
    start_detached,
    with_format,
)
from anyaudiobook.progress import (
    Advanced,
    ChapterNarrated,
    Finished,
    NarrationStarted,
    Packaging,
    ProgressEvent,
    Reading,
)
from anyaudiobook.tts import EdgeTTS
from tests.builders import FakeEngine, Para, write_docx

LONG = " ".join(["The story goes on."] * 60)


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """A two-chapter DOCX by Jane Doe called Lorem Ipsum."""
    return write_docx(
        tmp_path / "book.docx",
        [
            Para("Copyright © 2020 Jane Doe. All rights reserved."),
            Para("Chapter 1", "Heading1"),
            Para(LONG),
            Para("Chapter 2", "Heading1"),
            Para(LONG),
        ],
        title="Lorem Ipsum",
        author="Jane Doe",
    )


def make_job(book: Path, output: Path, **changes: object) -> ConversionJob:
    """Return an MP3 job for ``book`` with ``changes`` applied."""
    fields: dict[str, object] = {
        "source": book,
        "output": output,
        "output_format": "mp3",
        "voice": "pl-PL-ZofiaNeural",
    }
    return ConversionJob.model_validate(fields | changes)


@pytest.mark.parametrize(
    ("output_format", "expected"),
    [("mp3", "Jane Doe - Lorem"), ("m4b", "Jane Doe - Lorem.m4b")],
)
def test_default_output_is_named_after_the_book(
    output_format: str, expected: str
) -> None:
    assert default_output(Path("/books"), "Jane Doe - Lorem", output_format) == Path(
        "/books", expected
    )


@pytest.mark.parametrize(
    ("path", "output_format", "expected"),
    [
        ("/b/Book.m4b", "mp3", "/b/Book"),
        ("/b/Book.M4B", "mp3", "/b/Book"),
        ("/b/Book", "m4b", "/b/Book.m4b"),
        ("/b/Book.m4b", "m4b", "/b/Book.m4b"),
        ("/b/Book", "mp3", "/b/Book"),
        # Dots in a name are not an extension to replace.
        (
            "/b/J. R. R. Tolkien - The Hobbit",
            "m4b",
            "/b/J. R. R. Tolkien - The Hobbit.m4b",
        ),
        ("/b/.m4b", "mp3", "/b/.m4b"),
    ],
)
def test_with_format_swaps_the_extension(
    path: str, output_format: str, expected: str
) -> None:
    assert with_format(Path(path), output_format) == Path(expected)


def test_resolve_output_puts_a_single_file_inside_a_chosen_folder(
    tmp_path: Path,
) -> None:
    assert resolve_output(tmp_path, "m4b", "A - B") == tmp_path / "A - B.m4b"
    assert resolve_output(tmp_path, "mp3", "A - B") == tmp_path
    assert resolve_output(tmp_path / "x.m4b", "mp3", "A - B") == tmp_path / "x"


@pytest.mark.parametrize(
    ("output", "output_format", "expected"),
    [
        ("/b/Jane Doe - Lorem.m4b", "m4b", "/b/Jane Doe - Lorem.log"),
        (
            "/b/J. R. R. Tolkien - The Hobbit.m4b",
            "m4b",
            "/b/J. R. R. Tolkien - The Hobbit.log",
        ),
        ("/b/Jane Doe - Lorem", "mp3", "/b/Jane Doe - Lorem/Jane Doe - Lorem.log"),
    ],
)
def test_log_goes_next_to_the_audio(
    output: str, output_format: str, expected: str
) -> None:
    assert log_path(Path(output), output_format) == Path(expected)


def test_job_rejects_unknown_formats(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown output format"):
        make_job(tmp_path / "b.epub", tmp_path / "out", output_format="ogg")


def test_job_narrates_with_its_voice_and_prosody(tmp_path: Path) -> None:
    job = make_job(
        tmp_path / "b.epub", tmp_path / "out", prosody={"pitch": -10, "rate": 5}
    )

    assert job.engine() == EdgeTTS("pl-PL-ZofiaNeural", pitch="-10Hz", rate="+5%")
    assert job.command()[: len(WORKER_COMMAND)] == list(WORKER_COMMAND)
    assert ConversionJob.model_validate_json(job.command()[-1]) == job


def test_run_job_reports_every_stage(book: Path, tmp_path: Path) -> None:
    events: list[ProgressEvent] = []
    output = tmp_path / "Jane Doe - Lorem Ipsum"

    paths = run_job(make_job(book, output), events.append, FakeEngine())

    assert [p.name for p in paths] == ["1. Chapter 1.mp3", "2. Chapter 2.mp3"]
    kinds = [type(event) for event in events if not isinstance(event, Advanced)]
    assert kinds[:2] == [Reading, NarrationStarted]
    assert kinds[-2:] == [Packaging, Finished]
    assert kinds.count(ChapterNarrated) == 2
    started = next(e for e in events if isinstance(e, NarrationStarted))
    advanced = [e.characters for e in events if isinstance(e, Advanced)]
    assert advanced == sorted(advanced)
    assert advanced[-1] == started.characters
    assert events[-1] == Finished(paths=tuple(paths))
    assert not (output / f"{output.name}.log").exists()


def test_settings_reject_what_moved_to_the_form() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AdvancedSettings.model_validate({"pitch": "-10Hz"})


def test_run_job_writes_a_log_when_asked(book: Path, tmp_path: Path) -> None:
    job = make_job(book, tmp_path / "Lorem", log=True, prosody={"rate": 10})

    with job_log(job):
        run_job(job, lambda event: None, FakeEngine())

    log = job.log_path.read_text(encoding="utf-8")
    assert job.log_path == tmp_path / "Lorem" / "Lorem.log"
    assert "Voice:  pl-PL-ZofiaNeural (speed +10%, pitch +0Hz, volume +0%)" in log
    assert "What is narrated and skipped" in log
    assert "Narrated 2/2: Chapter 2" in log
    assert "Done: wrote 2 files" in log


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sessions")
def test_start_detached_runs_in_a_session_of_its_own() -> None:
    process = start_detached([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        deadline = time.monotonic() + 5
        while os.getsid(process.pid) != process.pid and time.monotonic() < deadline:
            time.sleep(0.01)
        assert os.getsid(process.pid) == process.pid != os.getsid(0)
    finally:
        process.terminate()
        process.wait(timeout=5)
