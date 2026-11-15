"""A conversion worker narrating with :class:`FakeEngine` instead of Edge TTS.

The TUI tests run :data:`COMMAND` in place of ``python -m anyaudiobook.worker``,
so conversions really happen in a separate process, minus the network.
"""

import sys
from pathlib import Path

from anyaudiobook.worker import run
from tests.builders import FakeEngine

_ROOT = str(Path(__file__).resolve().parent.parent)

COMMAND: tuple[str, ...] = (
    sys.executable,
    "-c",
    (
        f"import sys; sys.path.insert(0, {_ROOT!r});"
        " from tests.fake_worker import main; sys.exit(main())"
    ),
)
"""Runs a job like the real worker, from any working directory."""


def main() -> int:
    """Run the job given as the only argument, narrating silence."""
    return run(sys.argv[1:], engine=FakeEngine())
