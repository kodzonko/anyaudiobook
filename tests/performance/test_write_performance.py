"""How long writing an audiobook takes, per output format and book size.

Narration is done by :class:`SilentSpeech`, which writes as much audio as
Edge TTS would, in its format, but without the network. What is timed is
everything else a writer does: storing the audio, tagging it with the cover
and, for M4B, encoding and joining it with ffmpeg.
"""

import shutil
from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from anyaudiobook.errors import MissingToolError
from anyaudiobook.writers import WRITERS, writer_for
from anyaudiobook.writers.base import AudiobookWriter
from anyaudiobook.writers.m4b import duration
from tests.performance.books import (
    SIZES,
    BookSpec,
    SilentSpeech,
    benchmark_metadata,
    chapters,
    narration_seconds,
)

pytestmark = pytest.mark.performance

ROUNDS = 3
"""Writing a novel's M4B encodes ten hours of audio, so rounds are few."""


def _writer(output_format: str) -> AudiobookWriter:
    """Return the format's writer, skipping the test if it lacks a tool."""
    writer = writer_for(output_format)
    try:
        writer.check()
    except MissingToolError as error:
        pytest.skip(str(error))
    return writer


@pytest.mark.parametrize("spec", SIZES, ids=[spec.name for spec in SIZES])
@pytest.mark.parametrize("output_format", sorted(WRITERS))
def test_write_audiobook(
    benchmark: BenchmarkFixture, tmp_path: Path, output_format: str, spec: BookSpec
) -> None:
    """Narrate a generated book silently and package it, from an empty folder."""
    writer = _writer(output_format)
    output = tmp_path / "audiobook"
    hours = narration_seconds(spec) / 3600
    benchmark.group = f"write {spec.name} ({hours:.1f} h of audio)"
    benchmark.extra_info["audio_hours"] = round(hours, 2)

    paths = benchmark.pedantic(
        writer.write,
        args=(list(chapters(spec)), benchmark_metadata(), output, SilentSpeech()),
        setup=lambda: shutil.rmtree(output, ignore_errors=True),
        rounds=ROUNDS,
    )

    assert len(paths) == (1 if writer.file_suffix else spec.chapters)
    assert sum(map(duration, paths)) == pytest.approx(narration_seconds(spec), rel=0.01)
