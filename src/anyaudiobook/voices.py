"""The Edge TTS voices, grouped by language for choosing one."""

import re
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import edge_tts

_CAMEL_CASE = re.compile(r"(?<=[a-z])(?=[A-Z])")


@dataclass(frozen=True, slots=True)
class Voice:
    """One Edge TTS voice, as listed by ``edge-tts --list-voices``."""

    short_name: str
    """What :class:`anyaudiobook.tts.EdgeTTS` takes, e.g. ``pl-PL-ZofiaNeural``."""
    locale: str
    """e.g. ``pl-PL``."""
    gender: str
    friendly_name: str
    """e.g. ``Microsoft Zofia Online (Natural) - Polish (Poland)``."""

    @classmethod
    def from_edge(cls, data: Mapping[str, Any]) -> Voice:
        """Build a voice from an entry of :func:`edge_tts.list_voices`."""
        return cls(
            short_name=data["ShortName"],
            locale=data["Locale"],
            gender=data.get("Gender", ""),
            friendly_name=data.get("FriendlyName", ""),
        )

    @property
    def language_code(self) -> str:
        """The language part of the locale, e.g. ``pl``."""
        return self.locale.split("-")[0].lower()

    @property
    def language(self) -> str:
        """The language's English name, e.g. ``Polish``; the code if unknown."""
        return self._place()[0] or self.language_code

    @property
    def region(self) -> str:
        """Where the voice's accent is from, e.g. ``Poland``; may be empty."""
        return self._place()[1]

    @property
    def name(self) -> str:
        """The voice's own name, e.g. ``Zofia`` or ``Ava Multilingual``."""
        name = self.short_name.removeprefix(f"{self.locale}-").removesuffix("Neural")
        return _CAMEL_CASE.sub(" ", name) or self.short_name

    def _place(self) -> tuple[str, str]:
        """Split ``... - Polish (Poland)`` into ``("Polish", "Poland")``."""
        _, separator, place = self.friendly_name.rpartition(" - ")
        if not separator:
            return "", ""
        language, _, region = place.partition(" (")
        return language.strip(), region.removesuffix(")").strip()


VoiceFetcher = Callable[[], Awaitable[list[Voice]]]
"""Returns the voices on offer, e.g. :func:`fetch_voices`."""


@dataclass(frozen=True, slots=True)
class Language:
    """A language and its voices, from every region."""

    code: str
    """e.g. ``en``."""
    name: str
    """e.g. ``English``."""
    voices: tuple[Voice, ...]
    """Sorted by region, then name."""


def group_by_language(voices: Iterable[Voice]) -> list[Language]:
    """Group voices by language, sorted by the languages' names.

    A language is named as most of its voices name it.
    """
    groups: dict[str, list[Voice]] = {}
    for voice in voices:
        groups.setdefault(voice.language_code, []).append(voice)
    languages = [
        Language(
            code=code,
            name=Counter(voice.language for voice in group).most_common(1)[0][0],
            voices=tuple(sorted(group, key=lambda v: (v.region, v.name))),
        )
        for code, group in groups.items()
    ]
    return sorted(languages, key=lambda language: language.name.casefold())


async def fetch_voices() -> list[Voice]:
    """Download the list of voices from Microsoft.

    Raises:
        aiohttp.ClientError: If the service cannot be reached.
    """
    return [Voice.from_edge(entry) for entry in await edge_tts.list_voices()]
