"""Entry point: convert an ebook into an audiobook, interactively.

Run ``uv run python main.py`` and fill in the form; ``--detach`` converts in
the background and ``--log`` writes a log next to the audiobook. Choices and
the list of voices are remembered in ``anyaudiobook.db`` next to this file.

The settings below are the ones the form does not ask for; the voice's
speed, pitch and volume are set in the form.
"""

from pathlib import Path

from anyaudiobook.cli import main
from anyaudiobook.jobs import AdvancedSettings
from anyaudiobook.matter.models import DEFAULT_SKIP, FilterOptions

SETTINGS = AdvancedSettings(
    concurrency=5,  # chapters narrated at the same time
    # Front and back matter to leave out (see docs/filtering.md). For
    # example, DEFAULT_SKIP - {MatterKind.DEDICATION} (MatterKind is in
    # anyaudiobook.matter.models) also narrates the dedication.
    filter_options=FilterOptions(
        skip=DEFAULT_SKIP,
        include=(),  # regexes on file name or title to always narrate
        exclude=(),  # regexes on file name or title to never narrate
    ),
)

if __name__ == "__main__":
    main(app_dir=Path(__file__).resolve().parent, settings=SETTINGS)
