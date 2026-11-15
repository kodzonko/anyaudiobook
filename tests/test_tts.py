"""Tests for speech synthesis, with the Edge TTS service replaced."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from anyaudiobook import tts
from anyaudiobook.tts import EdgeTTS
from tests.conftest import ChapterFactory

pytestmark = pytest.mark.anyio


@dataclass
class CountingEngine:
    """A speech engine that records how many narrations overlap."""

    audio_suffix: ClassVar[str] = ".wav"
    active: int = 0
    peak: int = 0
    texts: list[str] = field(default_factory=list)

    async def synthesize(self, text: str, output_path: Path) -> None:
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

    async def save(self, path: str) -> None:
        """Write the text instead of audio."""
        Path(path).write_text(self.text)


async def test_get_available_voices_delegates_to_edge_tts() -> None:
    voices = [MagicMock()]
    with patch.object(tts.edge_tts, "list_voices", AsyncMock(return_value=voices)):
        assert await tts.get_available_voices() == voices


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
