"""Tests for speech synthesis, with the Edge TTS service replaced."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import anyio
import pytest

from anyaudiobook import tts
from anyaudiobook.progress import (
    Advanced,
    ChapterNarrated,
    ChapterStarted,
    NarrationStarted,
    ProgressEvent,
)
from anyaudiobook.tts import EdgeTTS, TextProgress
from tests.builders import FakeEngine
from tests.conftest import ChapterFactory

pytestmark = pytest.mark.anyio


@dataclass
class CountingEngine:
    """A speech engine that records how many narrations overlap."""

    audio_suffix: ClassVar[str] = ".wav"
    active: int = 0
    peak: int = 0
    texts: list[str] = field(default_factory=list)

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Write the text after a pause, tracking concurrency."""
        self.active += 1
        self.peak = max(self.peak, self.active)
        await anyio.sleep(0.01)
        output_path.write_text(text)
        self.texts.append(text)
        self.active -= 1


class RecordingCommunicate:
    """Stand-in for ``edge_tts.Communicate`` that records its arguments."""

    calls: ClassVar[list[tuple[str, str, dict[str, Any]]]] = []

    def __init__(self, text: str, voice: str, **settings: Any) -> None:
        """Record the arguments the real class would receive."""
        self.text = text
        RecordingCommunicate.calls.append((text, voice, settings))

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        """Send the text back as audio, sentence by sentence, with boundaries."""
        for sentence in self.text.split(". "):
            yield {"type": "SentenceBoundary", "text": sentence}
            yield {"type": "audio", "data": sentence.encode()}


async def test_edge_tts_passes_voice_settings(tmp_path: Path) -> None:
    RecordingCommunicate.calls = []
    engine = EdgeTTS("pl-PL-ZofiaNeural", pitch="-10Hz", rate="+5%")
    output = tmp_path / "chapter.mp3"

    with patch.object(tts.edge_tts, "Communicate", RecordingCommunicate):
        await engine.synthesize("Dzień dobry", output)

    assert RecordingCommunicate.calls == [
        (
            "Dzień dobry",
            "pl-PL-ZofiaNeural",
            {"pitch": "-10Hz", "rate": "+5%", "volume": "+0%"},
        )
    ]
    assert output.read_text() == "Dzień dobry"
    assert engine.audio_suffix == ".mp3"


async def test_synthesize_chapters_writes_one_file_per_chapter(
    tmp_path: Path, make_chapter: ChapterFactory
) -> None:
    chapters = [make_chapter(n, f"Chapter {n}", f"text {n}") for n in range(1, 11)]
    engine = CountingEngine()
    output_dir = tmp_path / "out"

    paths = await tts.synthesize_chapters(chapters, output_dir, engine, concurrency=3)

    assert [p.name for p in paths] == [
        f"{n:02d}. Chapter {n}.wav" for n in range(1, 11)
    ]
    assert all(p.read_text() == f"text {n}" for n, p in enumerate(paths, start=1))
    assert engine.peak == 3


async def test_edge_tts_reports_sentences_as_they_are_narrated(tmp_path: Path) -> None:
    progress: list[int] = []

    with patch.object(tts.edge_tts, "Communicate", RecordingCommunicate):
        await EdgeTTS("en-US-AvaNeural").synthesize(
            "One. Two two. Three", tmp_path / "c.mp3", progress.append
        )

    assert progress == [3, 10, 15]  # "One", "Two two", "Three"
    assert (tmp_path / "c.mp3").read_text() == "OneTwo twoThree"


async def test_synthesize_chapters_reports_progress(
    tmp_path: Path, make_chapter: ChapterFactory, fake_engine: FakeEngine
) -> None:
    chapters = [make_chapter(1, "One", "a" * 10), make_chapter(2, "Two", "b" * 30)]
    events: list[ProgressEvent] = []

    paths = await tts.synthesize_chapters(
        chapters, tmp_path, fake_engine, concurrency=1, progress=events.append
    )

    assert events == [
        NarrationStarted(chapters=2, characters=40),
        ChapterStarted(position=1, total=2, title="One"),
        Advanced(characters=5),
        Advanced(characters=10),
        ChapterNarrated(position=1, total=2, title="One", path=paths[0]),
        ChapterStarted(position=2, total=2, title="Two"),
        Advanced(characters=25),
        Advanced(characters=40),
        ChapterNarrated(position=2, total=2, title="Two", path=paths[1]),
    ]


async def test_synthesize_chapters_caps_overeager_progress(
    tmp_path: Path, make_chapter: ChapterFactory
) -> None:
    class Overcounting(CountingEngine):
        async def synthesize(
            self, text: str, output_path: Path, progress: TextProgress | None = None
        ) -> None:
            assert progress is not None
            progress(len(text) * 3)
            await super().synthesize(text, output_path)

    events: list[ProgressEvent] = []

    await tts.synthesize_chapters(
        [make_chapter(content="abcd")], tmp_path, Overcounting(), progress=events.append
    )

    assert [e.characters for e in events if isinstance(e, Advanced)] == [4, 4]
