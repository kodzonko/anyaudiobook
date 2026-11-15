# Performance tests

`tests/performance/` times every input format's reader and every output
format's writer with [pytest-benchmark](https://pytest-benchmark.readthedocs.io).
The tests carry the `performance` marker and are left out of a plain
`uv run pytest`, so they never slow down the test suite or skew coverage.

## Running

```sh
uv run pytest -m performance --no-cov                       # everything, ~2 min
uv run pytest -m performance --no-cov -k "not novel"        # the short book only, ~20 s
uv run pytest -m performance --no-cov -k "pdf or m4b"       # some formats
uv run pytest -m performance --no-cov --benchmark-disable   # each once, as plain tests
```

`--no-cov` matters: coverage tracing slows the code being timed, and the
coverage threshold would fail a run of these tests alone.

To catch a slowdown, save a baseline before a change and compare after it.
Baselines go to `.benchmarks/` (ignored by git), per machine and Python
version, since timings from different machines can't be compared:

```sh
uv run pytest -m performance --no-cov --benchmark-autosave
# ... change the code ...
uv run pytest -m performance --no-cov --benchmark-compare --benchmark-compare-fail=median:15%
```

## What is measured

Books are generated (`tests/performance/books.py`) in two sizes: `short`,
5 chapters and 10,000 words, and `novel`, 40 chapters and 100,000 words,
between a copyright page and acknowledgments. The text is pseudo-random
prose seeded by the size's name, so every run reads the same book. Each test
also checks the result (the chapters found, the length of the audio), so a
fast but wrong reader or writer fails.

| Test                   | Times                                                     | Grouped by           |
| ---------------------- | --------------------------------------------------------- | -------------------- |
| `test_read_book`       | `read_book()`: reading the file and choosing the chapters | book size            |
| `test_select_chapters` | choosing the chapters of a book already read              | book size            |
| `test_write_audiobook` | `AudiobookWriter.write()`: narration, tags, encoding      | hours of audio       |

- Input: EPUB, PDF, DOCX, DOC, MOBI 7, AZW3, TXT and HTML, one per reader
  code path. DOC needs LibreOffice or macOS `textutil` and Kindle books need
  Calibre's `ebook-convert` to be generated; without them those tests are
  skipped.
- Output: MP3 and M4B (skipped without ffmpeg), with a 300 kB cover.
  Narration is replaced by `SilentSpeech`, which writes as much silent audio
  as Edge TTS would (24 kHz, 48 kbit/s mono MP3, at about 150 words a
  minute: 1.1 h for the short book, 10.5 h for the novel), so the timings
  leave out only the network. M4B writes run 3 rounds, since one round of
  the novel encodes 10.5 hours of audio.

## What to expect

On an Apple Silicon Mac (November 2026), reading scales linearly with the
book's length. Reading the novel takes 0.2 s (EPUB, HTML) to 0.45 s (DOC),
and 1.5 s for PDF, which rebuilds the text from the page layout. Choosing
the chapters takes about 0.17 s of that for every format, so it is most of the
time for formats that are cheap to read. Writing MP3s costs little, since
they are written as the speech engine sends them. An M4B takes about 2 s per
hour of audio, nearly all of it ffmpeg's AAC encoding. None of this compares
with narration itself, which streams from Edge TTS at its own pace.
