# Architecture

ANYaudiobook is a script (`main.py`), not a library: the package under
`src/anyaudiobook/` has no public API to keep stable. A conversion is a pipeline of four steps. Each step is a small interface with
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
`synthesize(text, path)`. `EdgeTTS(voice, pitch, rate, volume)` is the built-in
one; `synthesize_chapters()` runs any engine concurrently. Tests use a fake
engine writing silent MP3s instead of patching Edge TTS.

## Packaging (`writers/`) — Strategy, Template Method

`AudiobookWriter.write()` is a template: `check()` the tools needed (before
hours of narration), narrate into `work_dir()`, then `package()` the files.
`Mp3Writer` narrates into the output directory and writes ID3 tags;
`M4bWriter` narrates into a temporary directory, joins the files with ffmpeg
(chapter markers from each file's duration) and tags the result with
mutagen. `WRITERS` (`writers/__init__.py`) maps format names to writers.

### Adding an output format

Write the writer in `writers/` and add it to the tuple building `WRITERS`:

```python
from anyaudiobook.writers.base import AudiobookWriter


class OpusWriter(AudiobookWriter):
    format_name = "opus"

    def work_dir(self, output): ...
    def package(self, tracks, metadata, output): ...
```

## Errors (`errors.py`)

`UnsupportedFormatError` (no reader or writer), `UnreadableBookError`
(scans, DRM, broken files) and `MissingToolError` (ffmpeg, LibreOffice) all
derive from `AnyAudiobookError`. External programs run through `tools.py`.
