# ANYaudiobook

<img src="docs/assets/logo.png" alt="anyaudiobook — an open book with pages shaped like sound waves" width="640">

A Python tool to convert EPUB ebooks to audiobooks using Microsoft Edge's Text-to-Speech engine.

## Tool setup

Install [mise](https://mise.jdx.dev/getting-started.html), then run from the repository root:

```sh
mise trust
mise install
```

Tool versions are declared in `mise.toml`. Activate mise in your shell, or prefix
project commands with `mise exec --` (for example, `mise exec -- uv --version`).

## Features

- Convert any ebook (currently only .epub) to .mp3 audiobook chapters
- Extract chapter titles and content automatically
- Process multiple chapters concurrently for faster conversion
- Organize output files with proper sequential numbering
- Support for multiple Microsoft Edge TTS voices
- Smart title detection and formatting

## How It Works

ANYaudiobook parses ebook files, extracts the text content chapter by chapter, and uses Edge TTS to generate natural-sounding audio files. The tool intelligently handles chapter titles, removes unnecessary elements like scripts and styles, and processes the content in parallel to speed up conversion.

## Usage

Edit the settings at the top of `main.py` (EPUB path, output directory, voice,
author, book title, cover image), then run:

```sh
uv run python main.py
```

It splits the EPUB into chapters, narrates each one into `NN. Title.mp3`, then
writes ID3 tags (artist, album, title, track number, cover art) to every file.

### As a library

```python
from anyaudiobook import EpubToAudiobookConverter, tag_chapters

converter = EpubToAudiobookConverter(
    "path/to/your/ebook.epub",
    "output_directory",
    "en-US-BrianNeural",  # English (US) male voice
)
converter.chunk_epub()  # extract chapters
converter.generate_audiobook(number_of_concurrent_tasks=10)
tag_chapters("output_directory", "Author Name", "Book Title", "cover.jpg")
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
