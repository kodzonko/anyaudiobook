"""How a voice speaks: its speed, pitch and volume (SSML calls this prosody).

Each is a change from the voice's own way of speaking, as Edge TTS takes it:
``+10%`` speed, ``-5Hz`` pitch, ``+0%`` volume. The form offers each as a
slider over the range of an :class:`Adjustment`.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True, slots=True)
class Adjustment:
    """One way of tuning a voice, and the values offered for it."""

    name: str
    """The :class:`Prosody` field, e.g. ``rate``."""
    label: str
    """What the form calls it, e.g. ``Speed``."""
    unit: str
    """``%`` or ``Hz``, as Edge TTS writes it."""
    minimum: int
    maximum: int
    step: int
    """How far one press of left or right moves the slider."""

    def edge(self, value: int) -> str:
        """Write ``value`` the way Edge TTS takes it, e.g. ``+10%``."""
        return f"{value:+d}{self.unit}"


RATE = Adjustment("rate", "Speed", "%", minimum=-50, maximum=100, step=5)
"""Speed: ``+25%`` is 1.25 times as fast, ``-50%`` half as fast."""
PITCH = Adjustment("pitch", "Pitch", "Hz", minimum=-50, maximum=50, step=5)
"""Pitch, in Hz up or down from the voice's own."""
VOLUME = Adjustment("volume", "Volume", "%", minimum=-50, maximum=50, step=5)
"""Volume, in percent louder or quieter."""
ADJUSTMENTS = (RATE, PITCH, VOLUME)
"""Everything a voice can be tuned by, in the order the form shows it."""


class Prosody(BaseModel):
    """The speed, pitch and volume a voice narrates with; 0 leaves each be."""

    model_config = ConfigDict(frozen=True)

    rate: int = Field(default=0, ge=RATE.minimum, le=RATE.maximum)
    """Speed change in percent, see :data:`RATE`."""
    pitch: int = Field(default=0, ge=PITCH.minimum, le=PITCH.maximum)
    """Pitch change in Hz, see :data:`PITCH`."""
    volume: int = Field(default=0, ge=VOLUME.minimum, le=VOLUME.maximum)
    """Volume change in percent, see :data:`VOLUME`."""

    def value(self, adjustment: Adjustment) -> int:
        """Return the value of ``adjustment``, e.g. 10 for a ``+10%`` speed."""
        return getattr(self, adjustment.name)

    def edge(self, adjustment: Adjustment) -> str:
        """Return the value of ``adjustment`` as Edge TTS takes it, e.g. ``+10%``."""
        return adjustment.edge(self.value(adjustment))

    def __str__(self) -> str:
        """Describe it, e.g. ``speed +10%, pitch -5Hz, volume +0%``."""
        return ", ".join(
            f"{adjustment.label.lower()} {self.edge(adjustment)}"
            for adjustment in ADJUSTMENTS
        )
