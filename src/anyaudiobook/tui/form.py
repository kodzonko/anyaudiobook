"""The screen where the user sets up a conversion."""

import sqlite3
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import anyio
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea
from textual.worker import get_current_worker

from anyaudiobook.converter import audiobook_metadata
from anyaudiobook.errors import AnyAudiobookError
from anyaudiobook.filenames import book_filename
from anyaudiobook.jobs import (
    ConversionJob,
    default_output,
    log_path,
    resolve_output,
    with_format,
)
from anyaudiobook.matter.models import FilterOptions
from anyaudiobook.models import BookMetadata
from anyaudiobook.prosody import ADJUSTMENTS, Adjustment, Prosody
from anyaudiobook.readers import READERS
from anyaudiobook.report import format_report
from anyaudiobook.selection import read_book
from anyaudiobook.store import Choices
from anyaudiobook.tools import play
from anyaudiobook.tui.config import TuiConfig
from anyaudiobook.tui.paths import parse_path_input
from anyaudiobook.tui.widgets import ChoiceList, Slider
from anyaudiobook.voices import Language, Voice, group_by_language
from anyaudiobook.writers import WRITERS, writer_for

VOICES_TIMEOUT = 30.0
"""Seconds to wait for the list of voices before keeping the cached one."""
DEFAULT_LANGUAGE = "en"
"""Language chosen when nothing was remembered."""
SAMPLE_CHARACTERS = 200
"""About how much of the ebook a preview reads: some ten seconds."""
PREVIEW_TIMEOUT = 30.0
"""Seconds to wait for a preview to be narrated."""
TUNING_HINT = (
    "Changes to the voice's own speed, pitch and volume: ← → adjust, 0 resets."
    " ctrl+t plays a sample."
)


def opening(text: str, limit: int = SAMPLE_CHARACTERS) -> str:
    """Return the start of ``text`` to read as a sample, about ``limit`` long.

    Whole sentences are kept when they fit; otherwise it is cut between words.
    """
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    end = max(cut.rfind(mark) for mark in (". ", "! ", "? ", "… "))
    if end >= limit // 3:
        return cut[: end + 1]
    return cut.rsplit(" ", 1)[0][:limit] + "…"


@dataclass(frozen=True, slots=True)
class BookPreview:
    """What the form shows about the chosen ebook once it is read."""

    source: Path
    metadata: BookMetadata
    chapters: int
    """How many chapters will be narrated."""
    skipped: int
    """How many parts of the book are left out."""
    report: str
    """What is narrated and skipped, and why, see :func:`format_report`."""
    sample: str
    """The opening of the first narrated chapter, read by the preview."""

    @classmethod
    def read(cls, source: Path, filter_options: FilterOptions) -> BookPreview:
        """Read the ebook at ``source`` and choose its chapters."""
        book = read_book(source, filter_options)
        metadata = audiobook_metadata(source, book.metadata)
        return cls(
            source=source,
            metadata=metadata,
            chapters=len(book.chapters),
            skipped=sum(not decision.narrate for decision in book.decisions),
            report=format_report(book.decisions),
            sample=opening(book.chapters[0].content if book.chapters else "")
            or metadata.title
            or source.stem,
        )

    @property
    def name(self) -> str:
        """The audiobook's file name without extension: ``Author - Title``."""
        return book_filename(self.metadata)

    @property
    def headline(self) -> str:
        """The book's title and authors, e.g. ``“Title” by Jane Doe``."""
        by = f" by {self.metadata.author}" if self.metadata.author else ""
        return f"“{self.metadata.title}”{by}"

    @property
    def summary(self) -> str:
        """A one-line description of the book and what will be narrated."""
        return (
            f"{self.headline}: {self.chapters} chapters to narrate,"
            f" {self.skipped} parts skipped (ctrl+r shows why)"
        )


StartConversion = Callable[[ConversionJob, BookPreview], None]
"""Starts the conversion the form was filled in for."""


def voice_label(voice: Voice) -> str:
    """Describe a voice in the voice list, e.g. ``Zofia  Female  Poland``."""
    return f"{voice.name:<20} {voice.gender:<7} {voice.region}"


class FormScreen(Screen[None]):
    """Choose the ebook, output format and file, language, voice and its tuning."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+s", "convert", "Convert", priority=True),
        Binding("ctrl+t", "preview", "Preview", priority=True),
        Binding("ctrl+r", "report", "Report", priority=True),
        Binding("escape", "stop_preview", "Stop preview", show=False),
    ]

    def __init__(self, config: TuiConfig, start: StartConversion) -> None:
        """Set up the form; ``start`` is called with the finished job."""
        super().__init__()
        self.config = config
        self.start = start
        self.preview: BookPreview | None = None
        """The chosen ebook, once read."""
        self.languages: dict[str, Language] = {}
        self.choices = Choices()
        self._suggested: Path | None = None

    def compose(self) -> ComposeResult:
        """Lay out the form, in the order it is filled in."""
        yield Header()
        with VerticalScroll(id="form"):
            yield Label("Ebook", classes="field")
            yield Input(
                placeholder="Paste or drop an ebook: EPUB, PDF, DOCX, DOC,"
                " MOBI, AZW3, TXT, HTML…",
                id="source",
            )
            yield Static(id="book", classes="note")
            yield Label("Output format", classes="field")
            yield ChoiceList(id="format")
            yield Label("Save as", classes="field")
            yield Input(placeholder="Chosen once the ebook is read", id="output")
            yield Static(id="output-note", classes="note")
            with Horizontal(id="pickers", classes="row"):
                with Vertical():
                    yield Label("Language", classes="field")
                    yield ChoiceList(placeholder="Loading voices…", id="language")
                with Vertical():
                    yield Label("Voice", classes="field")
                    yield ChoiceList(placeholder="Choose a language", id="voice")
            yield Static(id="voices-status", classes="note")
            with Horizontal(id="tuning", classes="row"):
                for adjustment in ADJUSTMENTS:
                    with Vertical():
                        yield Label(adjustment.label, classes="field")
                        yield Slider(
                            minimum=adjustment.minimum,
                            maximum=adjustment.maximum,
                            step=adjustment.step,
                            unit=adjustment.unit,
                            id=adjustment.name,
                        )
            yield Static(TUNING_HINT, id="tuning-note", classes="note")
            with Horizontal(id="actions"):
                yield Button("Convert", id="convert", variant="primary")
                yield Button("Preview", id="preview")
                yield Static(self._mode(), id="mode", classes="note")
        yield Footer()

    def on_mount(self) -> None:
        """Show what is remembered and start downloading the voices."""
        self.choices = self._from_store(self.config.store.load_choices, Choices())
        formats = self.query_one("#format", ChoiceList)
        formats.set_choices(
            [(name, writer.description) for name, writer in WRITERS.items()],
            self.choices.output_format,
        )
        for adjustment in ADJUSTMENTS:
            self._slider(adjustment).value = self.choices.prosody.value(adjustment)
        cached = self._from_store(self.config.store.voices, [])
        if cached:
            fetched_at = self._from_store(self.config.store.voices_fetched_at, None)
            when = f" from {fetched_at:%Y-%m-%d}" if fetched_at else ""
            self._show_voices(cached)
            self._say("#voices-status", f"{len(cached)} voices{when}; updating…")
        else:
            self._say("#voices-status", "Downloading the list of voices…")
        self.refresh_voices()
        self.query_one("#source", Input).focus()

    # --- the ebook ---------------------------------------------------------

    @on(Input.Changed, "#source")
    def _source_changed(self, event: Input.Changed) -> None:
        """Read the ebook as soon as the path points at one."""
        self.preview = None
        path = parse_path_input(event.value)
        if path is None:
            self._say("#book", "")
        elif not path.is_file():
            self._say("#book", f"No file at {path}", "error")
        elif path.suffix.lower() not in READERS:
            supported = ", ".join(sorted(READERS))
            self._say(
                "#book", f"Cannot read {path.suffix} files; use {supported}", "error"
            )
        else:
            self._say("#book", "Reading the ebook…", "busy")
            self.read_preview(path)

    @on(Input.Submitted, "#source")
    @on(Input.Submitted, "#output")
    def _next_field(self) -> None:
        """Move on with enter, like in a form."""
        self.focus_next()

    @work(thread=True, exclusive=True, group="book")
    def read_preview(self, path: Path) -> None:
        """Read the ebook in a thread, so the form stays responsive."""
        worker = get_current_worker()
        try:
            result: BookPreview | Exception = BookPreview.read(
                path, self.config.settings.filter_options
            )
        except Exception as error:  # noqa: BLE001 - shown in the form, whatever the reader raised
            result = error
        if not worker.is_cancelled:
            self.app.call_from_thread(self._show_preview, path, result)

    def _show_preview(self, path: Path, result: BookPreview | Exception) -> None:
        """Show the book that was read and suggest where to save it."""
        if parse_path_input(self.query_one("#source", Input).value) != path:
            return  # the user has chosen another file meanwhile
        if isinstance(result, Exception):
            self._say("#book", f"Cannot read this ebook: {result}", "error")
            return
        self.preview = result
        self._say("#book", result.summary, "ok")
        self._suggested = None
        self._refresh_output(new_book=True)

    def action_report(self) -> None:
        """Show what will be narrated and skipped, and why."""
        if self.preview is None:
            self.notify("Choose an ebook first.", severity="warning")
            return
        self.app.push_screen(ReportScreen(self.preview))

    # --- the output --------------------------------------------------------

    @on(ChoiceList.Chosen, "#format")
    def _format_chosen(self) -> None:
        """Fit the output path to the chosen format."""
        self._refresh_output()
        self.focus_next()

    @on(Input.Changed, "#output")
    def _output_changed(self) -> None:
        """Warn about overwriting, and say where the log goes."""
        self._describe_output()

    def _refresh_output(self, *, new_book: bool = False) -> None:
        """Keep the output path in step with the book and the format.

        A path the user has not edited follows the suggestion
        ``Author - Title`` next to the ebook; an edited one only gets its
        extension changed. A new book always starts from the suggestion.
        """
        output_format = self.query_one("#format", ChoiceList).value
        if output_format is None:
            return
        field = self.query_one("#output", Input)
        current = field.value.strip()
        suggested = (
            default_output(self.preview.source.parent, self.preview.name, output_format)
            if self.preview
            else None
        )
        untouched = not current or Path(current) == self._suggested
        if new_book or untouched:
            output = suggested
        else:
            output = with_format(Path(current).expanduser(), output_format)
        self._suggested = suggested
        if output is not None and str(output) != current:
            field.value = str(output)
        self._describe_output()

    def _output_path(self) -> Path | None:
        """The audiobook path the form describes, if it describes one."""
        output_format = self.query_one("#format", ChoiceList).value
        text = self.query_one("#output", Input).value.strip()
        if not text or output_format is None:
            return None
        name = self.preview.name if self.preview else "Audiobook"
        return resolve_output(Path(text).expanduser(), output_format, name).absolute()

    def _describe_output(self) -> None:
        """Say what writing to the output path will do."""
        output = self._output_path()
        output_format = self.query_one("#format", ChoiceList).value
        if output is None or output_format is None:
            self._say("#output-note", "")
            return
        notes = []
        tone = ""
        if output.is_file():
            notes.append("This file exists and will be replaced.")
            tone = "warning"
        elif output.is_dir() and any(output.iterdir()):
            notes.append("This folder is not empty; same-named chapters are replaced.")
            tone = "warning"
        if self.config.log:
            notes.append(f"Log: {log_path(output, output_format)}")
        self._say("#output-note", " ".join(notes), tone)

    # --- the voice ---------------------------------------------------------

    @work(exclusive=True, group="voices")
    async def refresh_voices(self) -> None:
        """Download the voices, then save and show them."""
        try:
            with anyio.fail_after(VOICES_TIMEOUT):
                voices = await self.config.fetch_voices()
        except Exception as error:  # noqa: BLE001 - offline, timeout and service errors alike
            reason = str(error) or type(error).__name__
            if self.languages:
                self._say(
                    "#voices-status",
                    f"Could not update the voices ({reason}); using the saved list.",
                    "warning",
                )
            else:
                self._say(
                    "#voices-status",
                    f"Could not download the voices ({reason}). Edge TTS needs"
                    " the internet: check the connection and restart.",
                    "error",
                )
            return
        self._from_store(lambda: self.config.store.save_voices(voices), None)
        self._show_voices(voices)
        self._say(
            "#voices-status",
            f"{len(voices)} voices in {len(self.languages)} languages, up to date.",
        )

    def _show_voices(self, voices: list[Voice]) -> None:
        """Offer the languages of ``voices``, keeping the current choice."""
        self.languages = {lang.code: lang for lang in group_by_language(voices)}
        language_list = self.query_one("#language", ChoiceList)
        current = language_list.value or self.choices.language or DEFAULT_LANGUAGE
        language_list.set_choices(
            [
                (lang.code, f"{lang.name} ({len(lang.voices)})")
                for lang in self.languages.values()
            ],
            current,
        )
        self._show_language_voices()

    @on(ChoiceList.Chosen, "#language")
    def _language_chosen(self) -> None:
        """Offer the voices of the chosen language."""
        self._show_language_voices()
        self.focus_next()

    @on(ChoiceList.Chosen, "#voice")
    def _voice_chosen(self) -> None:
        """Move on to the Convert button: the tuning is usually kept as it was."""
        self.query_one("#convert", Button).focus()

    def _show_language_voices(self) -> None:
        """Offer the chosen language's voices, the remembered one chosen."""
        code = self.query_one("#language", ChoiceList).value
        language = self.languages.get(code or "")
        voices = language.voices if language else ()
        voice_list = self.query_one("#voice", ChoiceList)
        names = {voice.short_name for voice in voices}
        current = voice_list.value if voice_list.value in names else None
        voice_list.set_choices(
            [(voice.short_name, voice_label(voice)) for voice in voices],
            current or self.choices.voices.get(code or ""),
        )

    # --- previewing --------------------------------------------------------

    @on(Button.Pressed, "#preview")
    def action_preview(self) -> None:
        """Narrate the opening of the ebook with the chosen voice, and play it."""
        voice = self.query_one("#voice", ChoiceList).value
        if self.preview is None:
            self.notify(
                "Choose an ebook first: the preview reads its opening.",
                severity="warning",
            )
            return
        if voice is None:
            self.notify("Choose a voice first.", severity="warning")
            return
        player = self.config.find_player()
        if player is None:
            self.notify(
                "Previews need an audio player: install ffmpeg (for ffplay) or mpv.",
                title="Cannot preview",
                severity="error",
            )
            return
        self.play_preview(self.preview.sample, voice, self._prosody(), player)

    def action_stop_preview(self) -> None:
        """Stop the preview that is being narrated or played."""
        self.workers.cancel_group(self, "preview")
        self._say("#tuning-note", TUNING_HINT)

    @work(exclusive=True, group="preview")
    async def play_preview(
        self, text: str, voice: str, prosody: Prosody, player: Sequence[str]
    ) -> None:
        """Narrate ``text`` into a temporary file and play it with ``player``.

        Starting another preview, or stopping, cancels this one, which also
        stops the player.
        """
        engine = self.config.preview_engine(voice, prosody)
        self._say("#tuning-note", f"Narrating a sample ({prosody})…", "busy")
        try:
            with tempfile.TemporaryDirectory(prefix="anyaudiobook-") as folder:
                path = Path(folder) / f"preview{engine.audio_suffix}"
                with anyio.fail_after(PREVIEW_TIMEOUT):
                    await engine.synthesize(text, path)
                self._say(
                    "#tuning-note", f"Playing a sample ({prosody}); esc stops it.", "ok"
                )
                await play(player, path)
        except Exception as error:  # noqa: BLE001 - offline, timeout and player errors alike
            reason = str(error) or type(error).__name__
            self._say("#tuning-note", f"Cannot preview: {reason}", "error")
            return
        self._say("#tuning-note", TUNING_HINT)

    # --- converting --------------------------------------------------------

    @on(Button.Pressed, "#convert")
    def action_convert(self) -> None:
        """Check the form, remember the choices and start converting."""
        job = self._job()
        if job is None:
            return
        self.action_stop_preview()
        language = self.query_one("#language", ChoiceList).value or ""
        self._from_store(
            lambda: self.config.store.save_choices(
                job.output_format, language, job.voice, job.prosody
            ),
            None,
        )
        self.choices = self._from_store(self.config.store.load_choices, self.choices)
        assert self.preview is not None  # checked by _job()
        self.start(job, self.preview)

    def _job(self) -> ConversionJob | None:
        """Return the job the form describes, or None after saying what is missing."""
        problems = []
        output_format = self.query_one("#format", ChoiceList).value
        voice = self.query_one("#voice", ChoiceList).value
        output = self._output_path()
        if self.preview is None:
            problems.append("Choose an ebook to convert.")
        if output is None:
            problems.append("Choose where to save the audiobook.")
        if voice is None:
            problems.append("Choose a voice; the list of voices has not loaded.")
        if output_format is not None:
            try:
                writer_for(output_format).check()
            except AnyAudiobookError as error:
                problems.append(str(error))
        if problems or not (self.preview and output and voice and output_format):
            self.notify("\n".join(problems), title="Not ready", severity="error")
            return None
        return ConversionJob(
            source=self.preview.source.absolute(),
            output=output,
            output_format=output_format,
            voice=voice,
            prosody=self._prosody(),
            log=self.config.log,
            settings=self.config.settings,
        )

    def _prosody(self) -> Prosody:
        """The speed, pitch and volume set with the sliders."""
        return Prosody.model_validate(
            {
                adjustment.name: self._slider(adjustment).value
                for adjustment in ADJUSTMENTS
            }
        )

    # --- helpers -----------------------------------------------------------

    def _slider(self, adjustment: Adjustment) -> Slider:
        """The slider setting ``adjustment``."""
        return self.query_one(f"#{adjustment.name}", Slider)

    def _mode(self) -> str:
        """Describe how the conversion will run, next to the Convert button."""
        how = (
            "Runs in the background (--detach): the terminal can be closed."
            if self.config.detach
            else "Shows progress here; --detach runs it in the background."
        )
        log = " A log file is written (--log)." if self.config.log else ""
        return how + log

    def _say(self, selector: str, text: str, tone: str = "") -> None:
        """Show ``text`` in a note, coloured by ``tone`` (error, ok, ...)."""
        note = self.query_one(selector, Static)
        note.update(Content(text))
        for name in ("error", "ok", "busy", "warning"):
            note.set_class(name == tone, f"-{name}")

    def _from_store[T](self, read: Callable[[], T], default: T) -> T:
        """Use the store, carrying on with ``default`` if it is unusable."""
        try:
            return read()
        except sqlite3.Error as error:
            self.notify(
                f"Cannot use {self.config.store.path}: {error}",
                title="Choices are not remembered",
                severity="warning",
            )
            return default


class ReportScreen(ModalScreen[None]):
    """What will be narrated and skipped, and why (``docs/filtering.md``)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,ctrl+r", "dismiss", "Close", priority=True)
    ]

    def __init__(self, preview: BookPreview) -> None:
        """Show the report of ``preview``."""
        super().__init__()
        self.preview = preview

    def compose(self) -> ComposeResult:
        """A scrollable, read-only table in a box."""
        with Vertical(id="report-box"):
            yield Label(Content(self.preview.headline), classes="field")
            yield TextArea(self.preview.report, read_only=True, id="report")
            yield Label("esc closes", classes="note")
