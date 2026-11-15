"""What the app remembers between runs, in an SQLite file next to ``main.py``.

Two things are kept: the choices of the last conversion (output format,
language, the voice last used for each language, and its speed, pitch and
volume), and the list of voices, so it shows at once while a fresh one
downloads.
"""

import sqlite3
from collections.abc import Generator, Iterable, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from anyaudiobook.prosody import Prosody
from anyaudiobook.voices import Voice

DB_NAME = "anyaudiobook.db"
"""The store's file name in the app's folder."""

_SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voices (
    short_name TEXT PRIMARY KEY,
    locale TEXT NOT NULL,
    gender TEXT NOT NULL,
    friendly_name TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
"""
_VOICE_PREFIX = "voice:"


@dataclass(frozen=True, slots=True)
class Choices:
    """The choices made for the last conversion."""

    output_format: str | None = None
    language: str | None = None
    """Language code, e.g. ``pl``."""
    voices: Mapping[str, str] = field(default_factory=dict)
    """The voice last chosen for each language code."""
    prosody: Prosody = field(default_factory=Prosody)
    """The speed, pitch and volume last narrated with."""


class Store:
    """The app's SQLite database: remembered choices and cached voices.

    Every method opens its own short-lived connection, so a store can be
    shared freely; the file and its tables are created on first use.
    """

    def __init__(self, path: Path) -> None:
        """Use the database at ``path``, see :meth:`in_folder`."""
        self.path = path

    @classmethod
    def in_folder(cls, folder: Path) -> Store:
        """Return the store kept in the app's ``folder``."""
        return cls(folder / DB_NAME)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        """Yield a connection inside a transaction, committed on success."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            if connection.execute("PRAGMA user_version").fetchone()[0] == 0:
                connection.executescript(_SCHEMA)
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            with connection:
                yield connection

    def load_choices(self) -> Choices:
        """Return the choices saved by :meth:`save_choices`."""
        with self._connect() as connection:
            rows = dict(connection.execute("SELECT key, value FROM preferences"))
        return Choices(
            output_format=rows.get("output_format"),
            language=rows.get("language"),
            voices={
                key.removeprefix(_VOICE_PREFIX): value
                for key, value in rows.items()
                if key.startswith(_VOICE_PREFIX)
            },
            prosody=_prosody(rows.get("prosody")),
        )

    def save_choices(
        self,
        output_format: str,
        language: str,
        voice: str,
        prosody: Prosody,
    ) -> None:
        """Remember the choices of a conversion; the voice for its language."""
        values = {
            "output_format": output_format,
            "language": language,
            f"{_VOICE_PREFIX}{language}": voice,
            "prosody": prosody.model_dump_json(),
        }
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO preferences (key, value) VALUES (?, ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                values.items(),
            )

    def voices(self) -> list[Voice]:
        """Return the voices saved by :meth:`save_voices`."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT short_name, locale, gender, friendly_name FROM voices"
                " ORDER BY short_name"
            ).fetchall()
        return [Voice(*row) for row in rows]

    def voices_fetched_at(self) -> datetime | None:
        """Return when the saved voices were downloaded, if they ever were."""
        with self._connect() as connection:
            (value,) = connection.execute(
                "SELECT MAX(fetched_at) FROM voices"
            ).fetchone()
        return datetime.fromisoformat(value) if value else None

    def save_voices(
        self, voices: Iterable[Voice], fetched_at: datetime | None = None
    ) -> None:
        """Replace the saved voices with ``voices``, downloaded at ``fetched_at``."""
        stamp = (fetched_at or datetime.now(UTC)).isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM voices")
            connection.executemany(
                "INSERT INTO voices VALUES (?, ?, ?, ?, ?)",
                (
                    (v.short_name, v.locale, v.gender, v.friendly_name, stamp)
                    for v in voices
                ),
            )


def _prosody(saved: str | None) -> Prosody:
    """Read back a saved :class:`Prosody`; a missing or unusable one is neutral.

    A value can become unusable when the ranges offered change.
    """
    if saved is None:
        return Prosody()
    try:
        return Prosody.model_validate_json(saved)
    except ValidationError:
        return Prosody()
