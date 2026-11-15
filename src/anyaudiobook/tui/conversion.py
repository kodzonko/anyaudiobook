"""The screen showing a conversion's progress.

The conversion runs in a worker process (:mod:`anyaudiobook.worker`); this
screen reads the progress events it writes to stdout. A separate process
keeps the TUI responsive while ebooks are parsed and lets "quit" really
stop the conversion.
"""

import subprocess
import time
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import ClassVar

import anyio
from anyio.abc import ByteReceiveStream, Process
from anyio.streams.buffered import BufferedByteReceiveStream
from pydantic import ValidationError
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Footer, Header, ProgressBar, RichLog, Static

from anyaudiobook.jobs import ConversionJob
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
    load_event,
)
from anyaudiobook.tui.form import BookPreview

QUIT_WINDOW = 3.0
"""Seconds within which a second ``q`` stops a running conversion."""
STOP_TIMEOUT = 5.0
"""Seconds the worker gets to clean up after SIGTERM before it is killed."""
_MAX_LINE = 1 << 20
_STDERR_TAIL = 4000


async def iter_lines(stream: ByteReceiveStream) -> AsyncIterator[bytes]:
    """Yield the lines of ``stream``, without their newlines, until it ends."""
    buffered = BufferedByteReceiveStream(stream)
    while True:
        try:
            yield await buffered.receive_until(b"\n", _MAX_LINE)
        except anyio.EndOfStream, anyio.IncompleteRead:
            return


def format_duration(seconds: float) -> str:
    """Format a duration as ``M:SS``, or ``H:MM:SS`` from an hour on."""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class ConversionScreen(Screen[None]):
    """Run a conversion job and show how it goes."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit_conversion", "Quit"),
        Binding("n", "new", "New conversion"),
    ]

    def __init__(
        self, job: ConversionJob, preview: BookPreview, command: Sequence[str]
    ) -> None:
        """Prepare to run ``command``, the worker process converting ``job``."""
        super().__init__()
        self.job = job
        self.preview = preview
        self.command = list(command)
        self.process: Process | None = None
        self.running = False
        self.paths: tuple[str, ...] = ()
        """What the worker wrote, once it has finished."""
        self.error: str | None = None
        self.ended = False
        """True once the worker has exited, whether it succeeded or not."""
        self._stage = "Starting…"
        self._chapters = 0
        self._narrated = 0
        self._active: dict[int, str] = {}
        self._stderr = b""
        self._started = time.monotonic()
        self._quit_requested_at: float | None = None

    def compose(self) -> ComposeResult:
        """A heading, the job, a progress bar, a status line and a log."""
        job = self.job
        details = [
            f"Voice: {job.voice} ({job.prosody})",
            f"Output: {job.output} ({job.output_format.upper()})",
        ]
        if job.log:
            details.append(f"Log: {job.log_path}")
        yield Header()
        with Vertical(id="conversion"):
            yield Static(
                Content(f"Converting {self.preview.headline}"), classes="field"
            )
            yield Static(Content("\n".join(details)), classes="note")
            yield ProgressBar(id="progress")
            yield Static(id="status")
            yield RichLog(id="log", wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        """Start the worker process."""
        self.convert()

    @work(exclusive=True, group="conversion")
    async def convert(self) -> None:
        """Run the worker, following its events until it exits."""
        self.running = True
        self.refresh_bindings()
        returncode: int | None = None
        try:
            async with await anyio.open_process(
                self.command, stdin=subprocess.DEVNULL
            ) as process:
                self.process = process
                try:
                    await self._follow(process)
                    returncode = await process.wait()
                except anyio.get_cancelled_exc_class():
                    with anyio.CancelScope(shield=True):
                        await self._stop(process)
                    raise
        except OSError as error:  # the worker could not be started
            self.error = str(error)
        self.running = False
        self._finish(returncode)

    async def _follow(self, process: Process) -> None:
        """Apply the events on the worker's stdout; keep its stderr's tail."""
        assert process.stdout is not None and process.stderr is not None

        async def drain_stderr(stream: ByteReceiveStream) -> None:
            async for chunk in stream:
                self._stderr = (self._stderr + chunk)[-_STDERR_TAIL:]

        async with anyio.create_task_group() as group:
            group.start_soon(drain_stderr, process.stderr)
            async for line in iter_lines(process.stdout):
                try:
                    event = load_event(line)
                except ValidationError:
                    continue  # not an event: something printed by a library
                self.apply(event)

    async def _stop(self, process: Process) -> None:
        """Ask the worker to stop, then make it."""
        if process.returncode is None:
            process.terminate()
            with anyio.move_on_after(STOP_TIMEOUT):
                await process.wait()

    def apply(self, event: ProgressEvent) -> None:
        """Update the progress bar, status and log for one event."""
        bar = self.query_one("#progress", ProgressBar)
        match event:
            case Reading():
                self._stage = "Reading the ebook…"
            case NarrationStarted(chapters=chapters, characters=characters):
                self._chapters = chapters
                bar.update(total=max(characters, 1), progress=0)
            case ChapterStarted(position=position, title=title):
                self._active[position] = title
            case ChapterNarrated(position=position):
                self._active.pop(position, None)
                self._narrated += 1
            case Advanced(characters=characters):
                bar.update(progress=characters)
            case Packaging(output_format=output_format):
                self._stage = f"Packaging the {output_format.upper()} audiobook…"
            case Finished(paths=paths):
                self.paths = tuple(str(path) for path in paths)
            case Failed(message=message):
                self.error = message
        if isinstance(event, (NarrationStarted, ChapterStarted, ChapterNarrated)):
            now = ", ".join(self._active[position] for position in sorted(self._active))
            self._stage = f"Narrated {self._narrated} of {self._chapters} chapters." + (
                f" Now: {now}" if now else ""
            )
        if line := describe(event):
            self.query_one("#log", RichLog).write(
                Text(f"{datetime.now():%H:%M:%S}  {line}")
            )
        self._status(self._stage)

    def _finish(self, returncode: int | None) -> None:
        """Say how the conversion ended."""
        elapsed = format_duration(time.monotonic() - self._started)
        log = self.query_one("#log", RichLog)
        if returncode == 0 and self.paths:
            bar = self.query_one("#progress", ProgressBar)
            bar.update(total=bar.total or 1, progress=bar.total or 1)
            where = self.paths[0] if len(self.paths) == 1 else str(self.job.output)
            self._status(f"✓ Done in {elapsed}: {where}", "ok")
            self.notify("The audiobook is ready.", title="Done")
        else:
            tail = self._stderr.decode(errors="replace").strip()
            reason = self.error or (tail.splitlines()[-1] if tail else "")
            reason = reason or f"the worker exited with status {returncode}"
            self._status(f"✗ Conversion failed after {elapsed}: {reason}", "error")
            if tail and not self.error:
                log.write(Text(tail))
        self.ended = True
        self.refresh_bindings()

    def _status(self, text: str, tone: str = "") -> None:
        """Show ``text`` under the progress bar."""
        status = self.query_one("#status", Static)
        status.update(Content(text))
        status.set_class(tone == "ok", "-ok")
        status.set_class(tone == "error", "-error")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Offer a new conversion only once this one has ended."""
        if action == "new":
            return not self.running
        return True

    async def action_quit_conversion(self) -> None:
        """Quit; while converting, only when ``q`` is pressed twice."""
        if self.running:
            now = time.monotonic()
            asked = self._quit_requested_at
            if asked is None or now - asked > QUIT_WINDOW:
                self._quit_requested_at = now
                self.notify(
                    "The conversion is still running. Press q again to stop it"
                    " and quit, or use --detach to convert in the background.",
                    severity="warning",
                    timeout=QUIT_WINDOW,
                )
                return
            if self.process is not None:
                await self._stop(self.process)
        self.app.exit()

    def action_new(self) -> None:
        """Go back to the form to convert another book."""
        self.app.pop_screen()
