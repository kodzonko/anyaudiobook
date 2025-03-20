# AnyAudiobook

A Python tool to convert EPUB ebooks to audiobooks using Microsoft Edge's Text-to-Speech engine.

## Features

- Convert any ebook (currently only .epub) to .mp3 audiobook chapters
- Extract chapter titles and content automatically
- Process multiple chapters concurrently for faster conversion
- Organize output files with proper sequential numbering
- Support for multiple Microsoft Edge TTS voices
- Smart title detection and formatting

## How It Works

AnyAudiobook parses ebook files, extracts the text content chapter by chapter, and uses Edge TTS to generate natural-sounding audio files. The tool intelligently handles chapter titles, removes unnecessary elements like scripts and styles, and processes the content in parallel to speed up conversion.

## Usage

```python
from anyaudiobook.main import EpubToAudiobookConverter

# Initialize the converter with the path to EPUB file, output directory, and voice
converter = EpubToAudiobookConverter(
    "path/to/your/ebook.epub",
    "output_directory",
    "en-US-BrianNeural"  # English (US) male voice
)

# Extract chapters from the EPUB file
converter.chunk_epub()

# Generate the audiobook (with 10 concurrent chapters processing)
converter.generate_audiobook(number_of_concurrent_tasks=10)
```

## Available Voices

You can get a list of all available voices:

```python
import asyncio
from anyaudiobook.main import get_available_voices

# Get all available voices
voices = asyncio.run(get_available_voices())
print(voices)
```

## Requirements

- Python 3.9+ (tested with py3.13)
- uv (or install manually against pyproject.toml) requirements)
- Windows 10/11 with Microsoft Edge installed
