"""Tests for speech synthesis, with Edge TTS mocked out."""

from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from anyaudiobook import tts
from tests.conftest import ChapterFactory

pytestmark = pytest.mark.anyio


class FakeCommunicate:
    """Stand-in for ``edge_tts.Communicate`` that records concurrency."""

    active: ClassVar[int] = 0
    peak: ClassVar[int] = 0
    calls: ClassVar[list[tuple[str, str, str]]] = []

    def __init__(self, text: str, voice: str, pitch: str) -> None:
        """Record the arguments the real class would receive."""
        self.text = text
        FakeCommunicate.calls.append((text, voice, pitch))

    async def save(self, path: str) -> None:
        """Write the text to ``path`` while tracking how many saves overlap."""
        FakeCommunicate.active += 1
        FakeCommunicate.peak = max(FakeCommunicate.peak, FakeCommunicate.active)
        await anyio.sleep(0.01)
        Path(path).write_text(self.text)
        FakeCommunicate.active -= 1


@pytest.fixture
def fake_communicate() -> Iterator[type[FakeCommunicate]]:
    """Patch Edge TTS with :class:`FakeCommunicate` and reset its counters."""
    FakeCommunicate.active = FakeCommunicate.peak = 0
    FakeCommunicate.calls = []
    with patch.object(tts.edge_tts, "Communicate", FakeCommunicate):
        yield FakeCommunicate


async def test_get_available_voices_delegates_to_edge_tts() -> None:
    voices = [MagicMock()]
    with patch.object(tts.edge_tts, "list_voices", AsyncMock(return_value=voices)):
        assert await tts.get_available_voices() == voices


async def test_synthesize_chapters_writes_one_file_per_chapter(
    tmp_path: Path,
    make_chapter: ChapterFactory,
    fake_communicate: type[FakeCommunicate],
) -> None:
    chapters = [make_chapter(n, f"Chapter {n}", f"text {n}") for n in range(1, 11)]
    output_dir = tmp_path / "out"

    paths = await tts.synthesize_chapters(
        chapters, output_dir, "voice", "-5Hz", concurrency=3
    )

    assert [p.name for p in paths] == [
        f"{n:02d}. Chapter {n}.mp3" for n in range(1, 11)
    ]
    assert all(p.read_text() == f"text {n}" for n, p in enumerate(paths, start=1))
    assert fake_communicate.calls[0] == ("text 1", "voice", "-5Hz")
    assert fake_communicate.peak == 3
