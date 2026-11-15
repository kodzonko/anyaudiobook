"""The command line: ``uv run python main.py [--detach] [--log]``."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from anyaudiobook.jobs import AdvancedSettings
from anyaudiobook.store import Store
from anyaudiobook.tui import AnyAudiobookApp, Detached, TuiConfig


def build_parser() -> argparse.ArgumentParser:
    """Return the parser of the command line options."""
    parser = argparse.ArgumentParser(
        description="Convert an ebook into an audiobook with Microsoft Edge's"
        " voices. Opens a form asking for the ebook, format, file and voice.",
    )
    parser.add_argument(
        "-d",
        "--detach",
        action="store_true",
        help="convert in the background, so the terminal can be closed",
    )
    parser.add_argument(
        "-l",
        "--log",
        action="store_true",
        help="write a log file next to the audiobook",
    )
    return parser


def detached_message(detached: Detached) -> str:
    """Tell the user where a background conversion will write its results."""
    job = detached.job
    lines = [
        (
            f"Converting in the background (process {detached.process.pid});"
            " you can close this terminal."
        ),
        f"Audiobook: {job.output}",
    ]
    if job.log:
        lines.append(f"Log:       {job.log_path}")
    else:
        lines.append("Run with --log to follow the conversion in a log file.")
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    app_dir: Path,
    settings: AdvancedSettings | None = None,
) -> None:
    """Parse the command line and run the TUI.

    Args:
        argv: The arguments; ``sys.argv[1:]`` if None.
        app_dir: The app's folder, where choices and voices are remembered.
        settings: The settings the TUI does not ask for.
    """
    args = build_parser().parse_args(argv)
    config = TuiConfig(
        store=Store.in_folder(app_dir),
        detach=args.detach,
        log=args.log,
        settings=settings or AdvancedSettings(),
    )
    result = AnyAudiobookApp(config).run()
    if isinstance(result, Detached):
        print(detached_message(result))
