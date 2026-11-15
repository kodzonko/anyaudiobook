"""Human-readable summary of what will be narrated and what skipped."""

from collections.abc import Sequence

from anyaudiobook.matter.models import Decision

_TITLE_WIDTH = 36
_FILE_WIDTH = 28


def _clip(text: str, width: int) -> str:
    """Shorten ``text`` to ``width`` characters, marking the cut with ``…``."""
    return text if len(text) <= width else text[: width - 1] + "…"


def format_report(decisions: Sequence[Decision]) -> str:
    """Render decisions as a table, one row per spine document.

    Example row::

        3  skip     copyright           112  Copyright      copy.xhtml   3 copyright …

    Args:
        decisions: The decisions from :func:`anyaudiobook.read_book`.

    Returns:
        The table followed by a one-line summary.
    """
    header = ("#", "action", "kind", "words", "title", "file", "reason")
    rows = [
        (
            str(decision.position),
            "narrate" if decision.narrate else "skip",
            decision.kind.value,
            str(decision.word_count),
            _clip(decision.title, _TITLE_WIDTH),
            _clip(decision.file_name, _FILE_WIDTH),
            decision.reason,
        )
        for decision in decisions
    ]
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(6)]
    right_aligned = {0, 3}
    lines = [
        "  ".join(
            [
                *(
                    cell.rjust(width) if column in right_aligned else cell.ljust(width)
                    for column, (cell, width) in enumerate(
                        zip(row[:6], widths, strict=True)
                    )
                ),
                row[6],
            ]
        ).rstrip()
        for row in (header, *rows)
    ]

    narrated = [decision for decision in decisions if decision.narrate]
    words = sum(decision.word_count for decision in narrated)
    lines.append(
        f"Narrating {len(narrated)} of {len(decisions)} documents "
        f"({words:,} words), skipping {len(decisions) - len(narrated)}."
    )
    return "\n".join(lines)
