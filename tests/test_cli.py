"""Tests for the command line."""

import subprocess
import sys
from pathlib import Path

import pytest

from anyaudiobook import cli
from anyaudiobook.jobs import AdvancedSettings, ConversionJob
from anyaudiobook.tui import AnyAudiobookApp, Detached, TuiConfig

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("argv", "detach", "log"),
    [
        ([], False, False),
        (["-d"], True, False),
        (["--detach", "--log"], True, True),
        (["-dl"], True, True),
        (["-l"], False, True),
    ],
)
def test_parser_reads_the_flags(argv: list[str], detach: bool, log: bool) -> None:
    args = cli.build_parser().parse_args(argv)

    assert (args.detach, args.log) == (detach, log)


def test_help_describes_the_flags() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--detach" in result.stdout
    assert "--log" in result.stdout


@pytest.fixture
def detached(tmp_path: Path) -> Detached:
    """A finished stand-in for a background conversion."""
    job = ConversionJob(
        source=tmp_path / "b.epub",
        output=tmp_path / "A - B.m4b",
        output_format="m4b",
        voice="en-US-AvaNeural",
        log=True,
    )
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return Detached(job, process)


def test_detached_message_says_where_to_look(
    detached: Detached, tmp_path: Path
) -> None:
    message = cli.detached_message(detached)

    assert f"process {detached.process.pid}" in message
    assert f"Audiobook: {tmp_path / 'A - B.m4b'}" in message
    assert f"Log:       {tmp_path / 'A - B.log'}" in message


def test_detached_message_suggests_a_log(detached: Detached) -> None:
    quiet = Detached(detached.job.model_copy(update={"log": False}), detached.process)

    assert "Run with --log" in cli.detached_message(quiet)


def test_main_runs_the_app_with_the_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    detached: Detached,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configs: list[TuiConfig] = []

    def run(app: AnyAudiobookApp) -> Detached:
        configs.append(app.config)
        return detached

    monkeypatch.setattr(AnyAudiobookApp, "run", run)
    settings = AdvancedSettings(concurrency=2)

    cli.main(["--detach", "--log"], app_dir=tmp_path, settings=settings)

    (config,) = configs
    assert (config.detach, config.log, config.settings) == (True, True, settings)
    assert config.store.path == tmp_path / "anyaudiobook.db"
    assert "Converting in the background" in capsys.readouterr().out
