"""How the TUI was started: the options and the services it uses."""

from collections.abc import Callable
from dataclasses import dataclass, field

from anyaudiobook.jobs import WORKER_COMMAND, AdvancedSettings
from anyaudiobook.prosody import Prosody
from anyaudiobook.store import Store
from anyaudiobook.tools import find_player
from anyaudiobook.tts import EdgeTTS, SpeechEngine
from anyaudiobook.voices import VoiceFetcher, fetch_voices


@dataclass(frozen=True, slots=True)
class TuiConfig:
    """Everything the TUI's screens need besides what the user enters."""

    store: Store
    """Where choices and voices are remembered."""
    detach: bool = False
    """``--detach``: start the conversion in the background and exit."""
    log: bool = False
    """``--log``: write a log file next to the audiobook."""
    settings: AdvancedSettings = field(default_factory=AdvancedSettings)
    """The settings from ``main.py`` that the form does not ask for."""
    fetch_voices: VoiceFetcher = fetch_voices
    """Downloads the list of voices (replaced in tests)."""
    worker_command: tuple[str, ...] = WORKER_COMMAND
    """Runs a job, given as JSON after these arguments (replaced in tests)."""
    preview_engine: Callable[[str, Prosody], SpeechEngine] = EdgeTTS.tuned
    """Narrates a preview with a voice and its tuning (replaced in tests)."""
    find_player: Callable[[], list[str] | None] = find_player
    """Finds the command playing a preview (replaced in tests)."""
