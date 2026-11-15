"""Tests for the SQLite store of choices and voices."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from anyaudiobook.prosody import Prosody
from anyaudiobook.store import DB_NAME, Choices, Store
from tests.test_voices import AVA, RYAN, ZOFIA


def test_store_starts_empty_in_a_new_folder(tmp_path: Path) -> None:
    store = Store.in_folder(tmp_path / "app")

    assert store.load_choices() == Choices()
    assert store.voices() == []
    assert store.voices_fetched_at() is None
    assert store.path == tmp_path / "app" / DB_NAME


def test_store_remembers_the_last_choices_and_a_voice_per_language(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "app.db")

    store.save_choices("m4b", "pl", ZOFIA.short_name, Prosody(pitch=-5))
    store.save_choices("mp3", "en", RYAN.short_name, Prosody(rate=15, volume=-10))

    assert Store(tmp_path / "app.db").load_choices() == Choices(
        output_format="mp3",
        language="en",
        voices={"pl": ZOFIA.short_name, "en": RYAN.short_name},
        prosody=Prosody(rate=15, volume=-10),
    )


@pytest.mark.parametrize(
    "saved", ['{"rate": 500}', "not json", '{"rate": "fast"}'], ids=str
)
def test_store_ignores_an_unusable_saved_prosody(tmp_path: Path, saved: str) -> None:
    store = Store(tmp_path / "app.db")
    store.save_choices("mp3", "en", RYAN.short_name, Prosody(rate=15))
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute(
            "UPDATE preferences SET value = ? WHERE key = 'prosody'", (saved,)
        )

    assert store.load_choices().prosody == Prosody()


def test_store_replaces_the_saved_voices(tmp_path: Path) -> None:
    store = Store(tmp_path / "app.db")
    first = datetime(2026, 1, 2, tzinfo=UTC)

    store.save_voices([ZOFIA, AVA], first)
    store.save_voices([RYAN, ZOFIA])

    assert store.voices() == [RYAN, ZOFIA]
    fetched_at = store.voices_fetched_at()
    assert fetched_at is not None and fetched_at > first
