"""Tests for the narrate/skip report."""

from anyaudiobook.matter.models import Decision, MatterKind
from anyaudiobook.report import format_report


def _decision(position: int, narrate: bool, title: str | None = None) -> Decision:
    """Build a narrated body page or a skipped copyright page."""
    return Decision(
        position=position,
        file_name=f"Text/p{position}.xhtml",
        title=title or f"Page {position}",
        kind=MatterKind.BODY if narrate else MatterKind.COPYRIGHT,
        reason="main text" if narrate else "3 copyright and imprint markers",
        narrate=narrate,
        word_count=1000 if narrate else 50,
    )


def test_format_report_lists_every_document_with_its_reason() -> None:
    report = format_report([_decision(1, False), _decision(2, True)])
    header, first, second, summary = report.splitlines()

    assert header.split() == ["#", "action", "kind", "words", "title", "file", "reason"]
    assert first.split()[:4] == ["1", "skip", "copyright", "50"]
    assert first.endswith("3 copyright and imprint markers")
    assert second.split()[:4] == ["2", "narrate", "body", "1000"]
    assert summary == "Narrating 1 of 2 documents (1,000 words), skipping 1."


def test_format_report_aligns_columns() -> None:
    lines = format_report([_decision(1, False), _decision(10, True)]).splitlines()

    assert lines[1].index("Page 1") == lines[2].index("Page 10")
    assert lines[1].startswith(" 1  ")
    assert lines[2].startswith("10  ")


def test_format_report_clips_long_titles() -> None:
    report = format_report([_decision(1, True, "x" * 100)])

    assert "x" * 35 + "…" in report
    assert "x" * 36 not in report


def test_format_report_of_empty_book() -> None:
    assert format_report([]).splitlines()[-1] == (
        "Narrating 0 of 0 documents (0 words), skipping 0."
    )
