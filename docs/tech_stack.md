# Preferences for technology stack

- using `anyio` (with asyncio backend) over pure `asyncio` for better concurrency and task management. Can't use other backends with `anyio` because Edge TTS relies on `aiohttp` which is asyncio-based.
- `ebooklib` reads EPUB; `beautifulsoup4` (with `lxml` for XML: NCX, OPF, DOCX properties) handles every HTML-based step.
- `PyMuPDF` reads PDFs: fast, gives fonts, sizes, superscript flags and positions per span, reads outlines and renders covers. Pinned to 1.x: 2.x makes `onnxruntime`, `numpy` and other layout-analysis packages (~110 MB) hard dependencies, which this project does not use. PyMuPDF is AGPL-3.0.
- `mammoth` converts DOCX to semantic HTML (headings from styles, footnotes collected at the end).
- `mobi` (KindleUnpack) unpacks MOBI/AZW/AZW3 into EPUB or HTML.
- `charset-normalizer` guesses the encoding of non-UTF-8 text files.
- `mutagen` writes ID3 (MP3) and MP4 (M4B) tags; `ffmpeg` (external) joins chapters into M4B.
- LibreOffice (external, optional) converts DOC/RTF/ODT to DOCX; macOS `textutil` is the fallback.
- `textual` draws the terminal UI: async like the rest (voices download while the form is filled in), with workers, screens and a test pilot.
- Conversions run in a worker process (`python -m anyaudiobook.worker`) streaming JSON progress events: the UI stays responsive while ebooks are parsed, quitting really stops the conversion, and `--detach` is the same process started in a session of its own.
- Voice previews play with an existing command-line player (`afplay`, `ffplay`, `mpv` or `mpg123`) rather than an audio library: no native dependency, nothing to install on macOS or where ffmpeg is installed for M4B.
- SQLite (`sqlite3`, standard library) remembers choices and caches the voice list in `anyaudiobook.db` next to `main.py`.
- Tests generate real books: `reportlab` for PDFs, hand-built DOCX zips, `ebooklib` EPUBs; Kindle files are committed fixtures made with Calibre (`tests/fixtures/make_kindle_fixtures.py`).
