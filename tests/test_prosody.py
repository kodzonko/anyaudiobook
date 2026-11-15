"""Tests for the speed, pitch and volume of a voice."""

import pytest
from pydantic import ValidationError

from anyaudiobook.prosody import ADJUSTMENTS, PITCH, RATE, VOLUME, Adjustment, Prosody


def test_prosody_is_written_the_way_edge_tts_takes_it() -> None:
    prosody = Prosody(rate=25, pitch=-5)

    assert [prosody.edge(a) for a in (RATE, PITCH, VOLUME)] == ["+25%", "-5Hz", "+0%"]
    assert str(prosody) == "speed +25%, pitch -5Hz, volume +0%"


@pytest.mark.parametrize("adjustment", ADJUSTMENTS, ids=lambda a: a.name)
def test_prosody_accepts_exactly_the_range_offered(adjustment: Adjustment) -> None:
    name = adjustment.name

    for value in (adjustment.minimum, 0, adjustment.maximum):
        assert Prosody.model_validate({name: value}).value(adjustment) == value
    for value in (adjustment.minimum - 1, adjustment.maximum + 1):
        with pytest.raises(ValidationError):
            Prosody.model_validate({name: value})
