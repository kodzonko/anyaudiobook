# ANYaudiobook

<img src="docs/assets/logo.png" alt="anyaudiobook — an open book with pages shaped like sound waves" width="640">

A Python tool to convert ebooks to audiobooks using Microsoft Edge's Text-to-Speech engine.

## Tool setup

Install [mise](https://mise.jdx.dev/getting-started.html), then run from the repository root:

```sh
mise trust
mise install
```

Tool versions are declared in `mise.toml`. Activate mise in your shell, or prefix
project commands with `mise exec --` (for example, `mise exec -- uv --version`).

## Features

- Reads EPUB, PDF (with a text layer), DOCX, DOC/RTF/ODT, MOBI/AZW/AZW3, TXT
  and HTML, see [docs/formats.md](docs/formats.md)
- Writes one tagged MP3 per chapter, or a single M4B audiobook with chapter
  markers
- Extracts chapter titles, and the book's title, authors and cover
- Skips front and back matter (table of contents, copyright, notes, index,
  acknowledgments, ads, ...) and strips footnotes, page numbers and running
  headers from the narration, see [docs/filtering.md](docs/filtering.md)
- Dry-run report of what will be narrated or skipped, and why
- Processes multiple chapters concurrently for faster conversion
- Supports every Microsoft Edge TTS voice, with pitch, rate and volume
- New input and output formats plug in without touching the rest, see
  [docs/architecture.md](docs/architecture.md)

## How It Works

ANYaudiobook reads the ebook into a common form (the book's parts as HTML),
recognises front and back matter from the book's own markup, the shape of
each part and its position in the book, leaves it out, narrates the remaining
chapters in parallel with Edge TTS and packages the audio as MP3 files or an
M4B.

## Usage

Edit the settings at the top of `main.py` (ebook path, output format and
location, voice, metadata overrides, what to skip), then run:

```sh
uv run python main.py
```

It prints which parts of the book it will narrate or skip and why, then
narrates each chapter. Set `DRY_RUN = True` to stop after the report.

### As a library

```python
from anyaudiobook import (
    DEFAULT_SKIP,
    AudiobookConverter,
    BookMetadata,
    EdgeTTS,
    FilterOptions,
    MatterKind,
)

converter = AudiobookConverter(
    "path/to/your/ebook.pdf",  # or .epub, .docx, .mobi, .azw3, .txt, ...
    "output_directory",
    EdgeTTS("en-US-BrianNeural"),  # English (US) male voice
    output_format="m4b",  # or "mp3" for one file per chapter
    filter_options=FilterOptions(skip=DEFAULT_SKIP - {MatterKind.DEDICATION}),
    metadata=BookMetadata(authors=("Author Name",)),  # overrides the ebook's own
)
print(converter.report())  # what is narrated or skipped, and why
converter.convert(concurrency=10)
```

### Available voices

```python
import anyio
from anyaudiobook import get_available_voices

voices = anyio.run(get_available_voices)
print(voices)
```

## Development

```sh
uv run pytest  # includes a coverage report; fails below 90%
uv run ruff check --fix
uv format
uv run ty check
```

## Requirements

- Python 3.14 (managed by mise)
- uv (managed by mise); install dependencies with `uv sync --locked`
- Internet access: Edge TTS is Microsoft's online speech service, so neither
  Windows nor the Edge browser is needed
- [ffmpeg](https://ffmpeg.org) for M4B output
- [LibreOffice](https://www.libreoffice.org) for DOC, RTF and ODT input (on
  macOS, the built-in `textutil` is used when LibreOffice is missing)
