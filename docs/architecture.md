# Architecture

ANYaudiobook is a program (`main.py`), not a library: the package under
`src/anyaudiobook/` has no public API to keep stable. A terminal UI collects
a conversion job and runs it in a worker process (see [Running a
conversion](#running-a-conversion)). A conversion is a pipeline of four steps. Each step is a small interface with
interchangeable implementations, so a new format touches one step only.

```text
ebook file ──read──▶ SourceBook ──select──▶ chapters ──narrate──▶ audio files ──package──▶ audiobook
            BookReader           FilterOptions       SpeechEngine            AudiobookWriter
            (per format)         (shared)            (EdgeTTS)               (mp3, m4b)
```

`AudiobookConverter` (`converter.py`) runs the steps; it is a facade over
the modules below.

## Common form: `SourceBook`

Every reader produces a `SourceBook` (`models.py`): `BookMetadata` (title,
authors, language, cover) and a list of `Document`s, each an HTML body with
its table of contents label. Everything after reading, from classifying front
and back matter (`matter/`) and cleaning up notes (`markup.py`) to choosing
chapters (`selection.py`), only sees this form. That is what keeps filtering
written once for all formats.

## Reading (`readers/`) — Strategy, Template Method

- `BookReader` is the interface: `read(path) -> SourceBook`.
- `READERS` (`readers/__init__.py`) maps file extensions to readers.
- `HtmlBookReader` is a template for every format that converts to one long
  HTML document. Its `read()` runs the shared steps, and subclasses only
  implement `load()` (and may refine `prepare()` and `section_name()`):
  1. parse the HTML and read `<head>` metadata
  2. mark entries of a separate table of contents (Kindle NCX)
  3. find headings in documents without heading markup
     (`readers/headings.py`: chapter-title patterns, known front/back matter
     titles, CSS font sizes)
  4. split into parts at TOC entries, else headings, else page breaks
     (`readers/splitting.py`)
  5. point links at the part now holding their target, so the classifier's
     link signals keep working
- `TextReader`, `DocxReader`, `HtmlReader`, `PdfReader` and `Mobi7Reader`
  are `HtmlBookReader`s. PDF outlines become TOC entries in the HTML they
  build, so PDFs split exactly like the others.
- `MobiReader` and `DocReader` convert and delegate: KF8 books unpack to an
  EPUB for `EpubReader`, DOC/RTF/ODT convert to DOCX for `DocxReader`.
- `readers/lines.py` (rejoining wrapped and hyphenated lines) is shared by
  TXT and PDF.

### Adding an input format

Write the reader in `readers/` and add it to the tuple building `READERS`:

```python
from pathlib import Path

from anyaudiobook.readers.base import HtmlBookReader, HtmlSource


class Fb2Reader(HtmlBookReader):
    suffixes = (".fb2",)

    def load(self, path: Path) -> HtmlSource:
        return HtmlSource(fb2_to_html(path.read_bytes()))
```

Produce HTML with `<h1>`/`<h2>` headings (or `data-toc-label` attributes
where TOC entries start) and the rest is shared.

## Narrating (`tts.py`) — Strategy

`SpeechEngine` is a protocol: an `audio_suffix` and an async
`synthesize(text, path, progress)`, which may report how many characters it
has narrated. `EdgeTTS(voice, pitch, rate, volume)` is the built-in one; it
streams the audio and counts the sentence boundaries Edge TTS sends.
`synthesize_chapters()` runs any engine concurrently and turns that into
progress events. Tests use a fake engine writing silent MP3s instead of
patching Edge TTS.

## Packaging (`writers/`) — Strategy, Template Method

`AudiobookWriter.write()` is a template: `check()` the tools needed (before
hours of narration), narrate into `work_dir()`, then `package()` the files.
`Mp3Writer` narrates into the output directory and writes ID3 tags;
`M4bWriter` narrates into a temporary directory, joins the files with ffmpeg
(chapter markers from each file's duration) and tags the result with
mutagen. `WRITERS` (`writers/__init__.py`) maps format names to writers.
Each writer has a `description` (its entry in the TUI's list) and a
`file_suffix` (`.m4b`; None for a folder of files), from which the default
output and log paths are derived (`jobs.py`).

### Adding an output format

Write the writer in `writers/` and add it to the tuple building `WRITERS`:

```python
from anyaudiobook.writers.base import AudiobookWriter


class OpusWriter(AudiobookWriter):
    format_name = "opus"
    description = "Opus - one file per chapter, in a folder"

    def work_dir(self, output): ...
    def package(self, tracks, metadata, output): ...
```

## Running a conversion

```text
main.py ─▶ cli.py ─▶ AnyAudiobookApp (tui/)
                       FormScreen ──ConversionJob──▶ worker process ──JSON events──▶ ConversionScreen
                         │  ▲                        python -m anyaudiobook.worker
                         ▼  │                        (--detach: own session, nobody reads)
                      Store (anyaudiobook.db)
```

- `progress.py`: what a conversion reports, as pydantic events (`Reading`,
  `NarrationStarted`, `ChapterStarted`, `ChapterNarrated`, `Advanced`,
  `Packaging`, `Finished`, `Failed`), passed to a `ProgressCallback` through
  `AudiobookConverter.convert()`, the writer and `synthesize_chapters()`.
  They serialise to one JSON line each.
- `jobs.py`: `ConversionJob` (ebook, output, format, voice, `--log`, and the
  `AdvancedSettings` from `main.py`) is everything a conversion needs, as
  JSON. `run_job()` runs one, logging each event; `job_log()` adds the log
  file. Also the output naming (`default_output`, `with_format`,
  `resolve_output`, `log_path`) and `start_detached()`.
- `worker.py`: the process running a job. Its stdout carries only events
  (file descriptor 1 is pointed at stderr, so libraries cannot corrupt the
  stream) and SIGTERM becomes `SystemExit`, so temporary files are removed.
- `tui/`: the Textual app. `FormScreen` reads the ebook in a thread for the
  preview and default name, downloads the voices (`voices.py`) on start and
  remembers choices (`store.py`). `ConversionScreen` runs the worker with
  `anyio.open_process` and applies its events. With `--detach` the app
  starts the worker with `start_detached()` and exits instead.
- `store.py`: SQLite tables `preferences` (last format, language, voice per
  language) and `voices` (the last downloaded list), versioned with
  `PRAGMA user_version`.

The TUI tests drive the real app with Textual's pilot and run real worker
processes (`tests/fake_worker.py`, with the silent fake engine); coverage
follows them into the subprocesses (`patch = ["subprocess"]`).

## Errors (`errors.py`)

`UnsupportedFormatError` (no reader or writer), `UnreadableBookError`
(scans, DRM, broken files) and `MissingToolError` (ffmpeg, LibreOffice) all
derive from `AnyAudiobookError`. External programs run through `tools.py`.
