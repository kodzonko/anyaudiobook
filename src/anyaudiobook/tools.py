"""External programs: LibreOffice and ffmpeg for some formats, a player for previews."""

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import anyio

from anyaudiobook.errors import AnyAudiobookError, MissingToolError

_STDERR_TAIL = 2000

_PLAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("afplay", ()),  # built into macOS
    ("ffplay", ("-nodisp", "-autoexit", "-loglevel", "error")),  # comes with ffmpeg
    ("mpv", ("--no-video", "--no-terminal")),  # leaves the terminal to the TUI
    ("mpg123", ("-q",)),
)
"""Command-line audio players, in order of preference, and their options."""


def find_tool(*names: str) -> str | None:
    """Return the path of the first of ``names`` found on ``PATH``."""
    for name in names:
        if path := shutil.which(name):
            return path
    return None


def find_player() -> list[str] | None:
    """Return the command playing an MP3 file given after it, or None.

    Every player runs without a window and without taking the terminal.
    """
    for name, options in _PLAYERS:
        if path := shutil.which(name):
            return [path, *options]
    return None


async def play(player: Sequence[str], audio: Path) -> None:
    """Play ``audio`` with ``player`` (see :func:`find_player`) to the end.

    Cancelling stops the player. This does not rely on
    :func:`anyio.run_process`, which waits for the program to exit when its
    task is cancelled the asyncio way, as Textual cancels workers.

    Raises:
        AnyAudiobookError: If the player fails.
    """
    with tempfile.TemporaryFile() as errors:
        process = await anyio.open_process(
            [*player, str(audio)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
        try:
            returncode = await process.wait()
        finally:
            if process.returncode is None:
                process.kill()
                with anyio.CancelScope(shield=True):
                    await process.wait()
        if returncode != 0:
            errors.seek(0)
            output = errors.read().decode(errors="replace").strip()[-_STDERR_TAIL:]
            name = Path(player[0]).name
            raise AnyAudiobookError(f"the player ({name}) failed: {output}")


def require_tool(purpose: str, *names: str, hint: str = "") -> str:
    """Return the path of the first of ``names`` found on ``PATH``.

    Args:
        purpose: What the tool is needed for, for the error message.
        names: Program names to look for, in order of preference.
        hint: How to install it, appended to the error message.

    Raises:
        MissingToolError: If none of them is installed.
    """
    path = find_tool(*names)
    if path is None:
        message = f"{purpose} needs {' or '.join(names)}, which is not installed."
        raise MissingToolError(f"{message} {hint}".strip())
    return path


def run_tool(args: Sequence[str], purpose: str) -> None:
    """Run an external program, raising a readable error if it fails.

    Args:
        args: The command line; ``args[0]`` is the program.
        purpose: What the program is doing, for the error message.

    Raises:
        AnyAudiobookError: If the program exits with an error.
    """
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        output = (error.stderr or error.stdout or "").strip()[-_STDERR_TAIL:]
        raise AnyAudiobookError(f"{purpose} failed: {output}") from error
