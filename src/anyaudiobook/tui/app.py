"""The Textual application: the form, then the conversion's progress."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from textual.app import App
from textual.screen import Screen

from anyaudiobook.jobs import ConversionJob, start_detached
from anyaudiobook.tui.config import TuiConfig
from anyaudiobook.tui.conversion import ConversionScreen
from anyaudiobook.tui.form import BookPreview, FormScreen


@dataclass(frozen=True, slots=True)
class Detached:
    """A conversion left running in the background (``--detach``)."""

    job: ConversionJob
    process: subprocess.Popen[bytes]


class AnyAudiobookApp(App[Detached | None]):
    """Convert an ebook into an audiobook, interactively.

    The app returns a :class:`Detached` when it started a conversion in the
    background, and None otherwise.
    """

    TITLE = "ANYaudiobook"
    CSS_PATH = Path(__file__).with_name("app.tcss")
    """Absolute, so subclasses elsewhere (in tests) find it too."""

    def __init__(self, config: TuiConfig) -> None:
        """Run with the options and services in ``config``."""
        super().__init__()
        self.config = config
        if config.detach:
            self.sub_title = "converts in the background"

    def get_default_screen(self) -> Screen:
        """Start with the form."""
        return FormScreen(self.config, self.start_conversion)

    def start_conversion(self, job: ConversionJob, preview: BookPreview) -> None:
        """Run ``job``: in the background and exit, or here with progress."""
        command = job.command(self.config.worker_command)
        if not self.config.detach:
            self.push_screen(ConversionScreen(job, preview, command))
            return
        try:
            process = start_detached(command)
        except OSError as error:
            self.notify(
                str(error), title="Cannot start the conversion", severity="error"
            )
        else:
            self.exit(Detached(job, process))
