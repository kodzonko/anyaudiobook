"""The process converting one book: ``python -m anyaudiobook.worker JOB``.

The TUI starts one per conversion, with a :class:`ConversionJob` as JSON for
``JOB``. Attached, the TUI reads the progress events the worker writes to
stdout, one JSON line each (:func:`anyaudiobook.progress.dump_event`), and
stops the worker with SIGTERM when the user quits. Detached (``--detach``),
the worker runs in its own session and nobody reads its output: the job's
log is the way to follow it.

A stray ``print`` from any library would corrupt the event stream (one
without a newline would merge into the next event), so the worker keeps the
real stdout for events and points file descriptor 1 at stderr before
converting.
"""

import logging
import os
import signal
import sys
from collections.abc import Sequence
from types import FrameType
from typing import TextIO

from anyaudiobook.jobs import ConversionJob, job_log, run_job
from anyaudiobook.progress import Failed, ProgressEvent, dump_event
from anyaudiobook.tts import SpeechEngine

logger = logging.getLogger("anyaudiobook")


def main(job_json: str, events: TextIO, engine: SpeechEngine | None = None) -> int:
    """Run the job described by ``job_json``, writing events to ``events``.

    Args:
        job_json: A :class:`ConversionJob` as JSON.
        events: Where the progress events go, one JSON line each.
        engine: Narrates instead of the job's Edge TTS voice (for tests).

    Returns:
        The exit status: 0 when the audiobook was written, 1 otherwise.
    """

    def send(event: ProgressEvent) -> None:
        try:
            events.write(dump_event(event) + "\n")
            events.flush()
        except OSError, ValueError:
            pass  # nobody is listening any more (closed pipe); keep converting

    job = ConversionJob.model_validate_json(job_json)
    with job_log(job):
        try:
            run_job(job, send, engine)
        except Exception as error:  # every failure is reported, not just ours
            logger.exception("Conversion failed")
            send(Failed(message=str(error) or type(error).__name__))
            return 1
    return 0


def run(argv: Sequence[str], engine: SpeechEngine | None = None) -> int:
    """Run as a process: claim stdout for events and stop cleanly on SIGTERM.

    Args:
        argv: The arguments after the program name: the job's JSON.
        engine: Narrates instead of the job's Edge TTS voice (for tests).
    """
    if len(argv) != 1:
        print("usage: python -m anyaudiobook.worker JOB_JSON", file=sys.stderr)
        return 2
    events = _claim_stdout()
    signal.signal(signal.SIGTERM, _exit)
    return main(argv[0], events, engine)


def _claim_stdout() -> TextIO:
    """Return the real stdout for events and send everything else to stderr."""
    sys.stdout.flush()
    events = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)
    return events


def _exit(signum: int, frame: FrameType | None) -> None:
    """Turn SIGTERM into SystemExit so temporary files are cleaned up."""
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
