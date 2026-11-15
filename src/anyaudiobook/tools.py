"""Run the external programs some formats need (LibreOffice, ffmpeg)."""

import shutil
import subprocess
from collections.abc import Sequence

from anyaudiobook.errors import AnyAudiobookError, MissingToolError

_STDERR_TAIL = 2000


def find_tool(*names: str) -> str | None:
    """Return the path of the first of ``names`` found on ``PATH``."""
    for name in names:
        if path := shutil.which(name):
            return path
    return None


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
