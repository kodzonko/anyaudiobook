"""Tests for the voice catalogue."""

from typing import Any
from unittest.mock import patch

import pytest

from anyaudiobook import voices
from anyaudiobook.voices import Voice, fetch_voices, group_by_language

ZOFIA = Voice(
    "pl-PL-ZofiaNeural",
    "pl-PL",
    "Female",
    "Microsoft Zofia Online (Natural) - Polish (Poland)",
)
AVA = Voice(
    "en-US-AvaMultilingualNeural",
    "en-US",
    "Female",
    "Microsoft AvaMultilingual Online (Natural) - English (United States)",
)
RYAN = Voice(
    "en-GB-RyanNeural",
    "en-GB",
    "Male",
    "Microsoft Ryan Online (Natural) - English (United Kingdom)",
)
XIAOBEI = Voice(
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-liaoning",
    "Female",
    "Microsoft Xiaobei Online (Natural) - Chinese (Northeastern Mandarin)",
)
ODD = Voice("xx-XX-Odd", "xx-XX", "Male", "Odd voice")


@pytest.mark.parametrize(
    ("voice", "name", "language", "region", "code"),
    [
        (ZOFIA, "Zofia", "Polish", "Poland", "pl"),
        (AVA, "Ava Multilingual", "English", "United States", "en"),
        (XIAOBEI, "Xiaobei", "Chinese", "Northeastern Mandarin", "zh"),
        (ODD, "Odd", "xx", "", "xx"),
    ],
)
def test_voice_describes_itself(
    voice: Voice, name: str, language: str, region: str, code: str
) -> None:
    assert (voice.name, voice.language, voice.region, voice.language_code) == (
        name,
        language,
        region,
        code,
    )


def test_group_by_language_sorts_languages_and_voices() -> None:
    languages = group_by_language([ZOFIA, AVA, RYAN, XIAOBEI])

    assert [(lang.code, lang.name) for lang in languages] == [
        ("zh", "Chinese"),
        ("en", "English"),
        ("pl", "Polish"),
    ]
    assert languages[1].voices == (RYAN, AVA)  # United Kingdom < United States


@pytest.mark.anyio
async def test_fetch_voices_reads_edge_tts_list() -> None:
    entries: list[dict[str, Any]] = [
        {
            "ShortName": ZOFIA.short_name,
            "Locale": ZOFIA.locale,
            "Gender": ZOFIA.gender,
            "FriendlyName": ZOFIA.friendly_name,
        },
        {"ShortName": "xx-XX-OddNeural", "Locale": "xx-XX"},
    ]

    async def list_voices() -> list[dict[str, Any]]:
        return entries

    with patch.object(voices.edge_tts, "list_voices", list_voices):
        fetched = await fetch_voices()

    assert fetched == [ZOFIA, Voice("xx-XX-OddNeural", "xx-XX", "", "")]
