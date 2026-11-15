"""Tests for the SQLite store of choices and voices."""

from datetime import UTC, datetime
from pathlib import Path

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

    store.save_choices("m4b", "pl", ZOFIA.short_name)
    store.save_choices("mp3", "en", RYAN.short_name)

    assert Store(tmp_path / "app.db").load_choices() == Choices(
        output_format="mp3",
        language="en",
        voices={"pl": ZOFIA.short_name, "en": RYAN.short_name},
    )


def test_store_replaces_the_saved_voices(tmp_path: Path) -> None:
    store = Store(tmp_path / "app.db")
    first = datetime(2026, 1, 2, tzinfo=UTC)

    store.save_voices([ZOFIA, AVA], first)
    store.save_voices([RYAN, ZOFIA])

    assert store.voices() == [RYAN, ZOFIA]
    fetched_at = store.voices_fetched_at()
    assert fetched_at is not None and fetched_at > first
