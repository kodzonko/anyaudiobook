"""A conversion job: everything a conversion needs, runnable anywhere.

The TUI fills in a :class:`ConversionJob` and hands it, as JSON, to a worker
process (:mod:`anyaudiobook.worker`) that calls :func:`run_job`. The
functions here also decide where an audiobook and its log are written.
"""

import logging
import subprocess
import sys
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from anyaudiobook.converter import AudiobookConverter
from anyaudiobook.matter.models import FilterOptions
from anyaudiobook.progress import (
    Finished,
    ProgressCallback,
    ProgressEvent,
    Reading,
    describe,
)
from anyaudiobook.prosody import Prosody
from anyaudiobook.tts import EdgeTTS, SpeechEngine
from anyaudiobook.writers import WRITERS

logger = logging.getLogger("anyaudiobook")

WORKER_COMMAND: tuple[str, ...] = (sys.executable, "-m", "anyaudiobook.worker")
"""The command running a job; the job's JSON is appended as its argument."""

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"


class AdvancedSettings(BaseModel):
    """Settings the TUI does not ask for; set them in ``main.py``.

    Unknown settings are rejected, so a misspelt one (or one that moved to
    the form, like ``pitch``) does not go unnoticed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    concurrency: int = Field(default=5, ge=1)
    """Most chapters narrated at the same time."""
    filter_options: FilterOptions = FilterOptions()
    """What to narrate, see ``docs/filtering.md``."""


class ConversionJob(BaseModel):
    """One ebook to convert into one audiobook."""

    model_config = ConfigDict(frozen=True)

    source: Path
    """The ebook file."""
    output: Path
    """The audiobook: a folder for MP3 chapters, an ``.m4b`` file for M4B."""
    output_format: str
    """A key of :data:`anyaudiobook.writers.WRITERS`, e.g. ``m4b``."""
    voice: str
    """Edge TTS voice short name, e.g. ``pl-PL-ZofiaNeural``."""
    prosody: Prosody = Prosody()
    """The voice's speed, pitch and volume."""
    log: bool = False
    """Write a log file next to the audiobook, see :attr:`log_path`."""
    settings: AdvancedSettings = AdvancedSettings()

    @field_validator("output_format")
    @classmethod
    def _known_format(cls, value: str) -> str:
        """Reject output formats no writer handles."""
        if value not in WRITERS:
            raise ValueError(f"unknown output format {value!r}")
        return value

    @property
    def log_path(self) -> Path:
        """Where the log goes when :attr:`log` is set."""
        return log_path(self.output, self.output_format)

    def engine(self) -> EdgeTTS:
        """Return the speech engine narrating this job."""
        return EdgeTTS.tuned(self.voice, self.prosody)

    def command(self, worker: Sequence[str] = WORKER_COMMAND) -> list[str]:
        """Return the command line of a worker process running this job."""
        return [*worker, self.model_dump_json()]


def default_output(folder: Path, name: str, output_format: str) -> Path:
    """Return the audiobook path for a book called ``name`` in ``folder``.

    For example ``folder/Author - Title.m4b`` for M4B, and the folder
    ``folder/Author - Title`` holding the chapter files for MP3.
    """
    return with_format(folder / name, output_format)


def with_format(path: Path, output_format: str) -> Path:
    """Make an output path fit ``output_format``: swap the file extension.

    ``Book.m4b`` becomes the folder ``Book`` for MP3 and ``Book`` becomes
    ``Book.m4b`` for M4B. Extensions are added to the name rather than
    replaced with :meth:`Path.with_suffix`, which would treat the dots in
    ``J. R. R. Tolkien - The Hobbit`` as an extension.
    """
    name = path.name
    for writer in WRITERS.values():
        name = _strip_suffix(name, writer.file_suffix)
    if not name:
        return path
    return path.with_name(name + (WRITERS[output_format].file_suffix or ""))


def resolve_output(path: Path, output_format: str, name: str) -> Path:
    """Turn the output the user chose into the audiobook path.

    An existing folder chosen for a single-file format gets a file named
    ``name`` inside it; any other path is fitted with :func:`with_format`.
    """
    suffix = WRITERS[output_format].file_suffix
    if suffix and path.is_dir():
        return path / (name + suffix)
    return with_format(path, output_format)


def log_path(output: Path, output_format: str) -> Path:
    """Return the log file of an audiobook, next to its audio files.

    ``Author - Title.log`` beside an M4B, or inside an MP3 chapter folder.
    """
    suffix = WRITERS[output_format].file_suffix
    if suffix:
        return output.with_name(f"{_strip_suffix(output.name, suffix)}.log")
    return output / f"{output.name}.log"


def _strip_suffix(name: str, suffix: str | None) -> str:
    """Remove ``suffix`` from the end of ``name``, ignoring case."""
    if suffix and name.lower().endswith(suffix) and len(name) > len(suffix):
        return name[: -len(suffix)]
    return name


def run_job(
    job: ConversionJob, progress: ProgressCallback, engine: SpeechEngine | None = None
) -> list[Path]:
    """Read the ebook, narrate it and write the audiobook.

    Every event is also logged, see :func:`job_log`.

    Args:
        job: What to convert.
        progress: Told how the conversion goes, ending with :class:`Finished`.
        engine: Narrates instead of the job's Edge TTS voice (for tests).

    Returns:
        The files written.
    """

    def report(event: ProgressEvent) -> None:
        if line := describe(event):
            logger.info("%s", line)
        progress(event)

    converter = AudiobookConverter(
        job.source,
        job.output,
        engine or job.engine(),
        output_format=job.output_format,
        filter_options=job.settings.filter_options,
    )
    report(Reading())
    converter.read()
    logger.info("What is narrated and skipped:\n%s", converter.report())
    paths = converter.convert(job.settings.concurrency, report)
    report(Finished(paths=tuple(paths)))
    return paths


@contextmanager
def job_log(job: ConversionJob) -> Generator[None]:
    """Log to :attr:`ConversionJob.log_path` while in the block, if the job asks.

    The log starts with the job's settings and gets one line per progress
    event (see :func:`anyaudiobook.progress.describe`) and the traceback of
    any failure.
    """
    if not job.log:
        yield
        return
    path = job.log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("Ebook:  %s", job.source)
        logger.info("Output: %s (%s)", job.output, job.output_format.upper())
        logger.info("Voice:  %s (%s)", job.voice, job.prosody)
        logger.info("Settings: %s", job.settings.model_dump_json())
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()


def start_detached(command: Sequence[str]) -> subprocess.Popen[bytes]:
    """Start ``command`` so that it outlives this terminal.

    On POSIX it runs in a new session, so closing the terminal does not
    send it SIGHUP; on Windows it gets no console and its own process group.
    Its input and output are discarded: use the job's log to follow it.
    """
    null = subprocess.DEVNULL
    if sys.platform == "win32":
        return subprocess.Popen(
            command,
            stdin=null,
            stdout=null,
            stderr=null,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(
        command, stdin=null, stdout=null, stderr=null, start_new_session=True
    )
