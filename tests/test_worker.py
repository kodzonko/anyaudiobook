"""Tests for the worker process that runs conversion jobs."""

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from anyaudiobook import worker
from anyaudiobook.jobs import ConversionJob
from anyaudiobook.progress import Failed, Finished, Reading, load_event
from tests.builders import FakeEngine
from tests.conftest import FIXTURES
from tests.fake_worker import COMMAND


def job_json(source: Path, output: Path, **changes: object) -> str:
    """Return an MP3 job for ``source`` as JSON."""
    fields: dict[str, object] = {
        "source": source,
        "output": output,
        "output_format": "mp3",
        "voice": "en-US-AvaNeural",
    }
    return ConversionJob.model_validate(fields | changes).model_dump_json()


def test_main_streams_events_as_json_lines(epub_file: Path, tmp_path: Path) -> None:
    events = io.StringIO()

    status = worker.main(job_json(epub_file, tmp_path / "out"), events, FakeEngine())

    parsed = [load_event(line) for line in events.getvalue().splitlines()]
    assert status == 0
    assert parsed[0] == Reading()
    assert isinstance(parsed[-1], Finished)
    assert [p.name for p in parsed[-1].paths] == ["1. Beginning.mp3", "2. The End.mp3"]


def test_main_reports_failures_and_logs_them(tmp_path: Path) -> None:
    events = io.StringIO()
    job = job_json(tmp_path / "missing.epub", tmp_path / "out", log=True)

    status = worker.main(job, events, FakeEngine())

    last = load_event(events.getvalue().splitlines()[-1])
    assert status == 1
    assert isinstance(last, Failed)
    assert "No such ebook" in last.message
    log = (tmp_path / "out" / "out.log").read_text(encoding="utf-8")
    assert "Conversion failed" in log
    assert "Traceback" in log


def test_main_keeps_converting_when_nobody_listens(
    epub_file: Path, tmp_path: Path
) -> None:
    events = io.StringIO()
    events.close()  # like a TUI that went away

    status = worker.main(job_json(epub_file, tmp_path / "out"), events, FakeEngine())

    assert status == 0
    assert (tmp_path / "out" / "2. The End.mp3").exists()


def test_run_needs_exactly_one_argument(capsys: pytest.CaptureFixture[str]) -> None:
    assert worker.run([]) == 2
    assert "usage" in capsys.readouterr().err


def test_claimed_stdout_carries_only_events() -> None:
    code = (
        "import sys; from anyaudiobook.worker import _claim_stdout;"
        " events = _claim_stdout(); print('library chatter', end='');"
        " events.write('event\\n'); events.flush()"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout == "event\n"
    assert result.stderr == "library chatter"


def test_worker_process_converts_a_kindle_book(tmp_path: Path) -> None:
    source = Path(shutil.copy(FIXTURES / "book.mobi", tmp_path / "book.mobi"))
    output = tmp_path / "out"

    result = subprocess.run(
        [*COMMAND, job_json(source, output, log=True)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert all(json.loads(line)["kind"] for line in lines)
    assert isinstance(load_event(lines[-1]), Finished)
    assert (output / "out.log").exists()
