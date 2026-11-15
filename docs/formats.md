# Input and output formats

## Input

The reader is chosen by file extension. Every reader turns the book into the
same form, a list of parts in reading order (each an HTML body) plus the
book's metadata, so [skipping front and back matter](filtering.md) works the
same for all of them.

| Extension                                 | Reader        | Parts come from                                                       | Metadata                                |
| ----------------------------------------- | ------------- | --------------------------------------------------------------------- | --------------------------------------- |
| `.epub`                                   | `EpubReader`  | spine documents                                                       | title, authors, language, cover         |
| `.pdf`                                    | `PdfReader`   | outline (bookmarks), else headings found by font size                 | title, authors; cover if page 1 has an image |
| `.docx`                                   | `DocxReader`  | Word heading styles, else chapter-like paragraphs                     | title, authors, language                |
| `.doc`, `.rtf`, `.odt`                    | `DocReader`   | converted to DOCX by LibreOffice (or to HTML by macOS `textutil`)     | as the converted file                   |
| `.mobi`, `.azw`, `.azw3`, `.kf8`, `.prc`  | `MobiReader`  | KF8/AZW3: unpacked EPUB; MOBI 7: NCX table of contents                | title, authors, language, cover         |
| `.txt`, `.text`                           | `TextReader`  | chapter titles (`Chapter 3`, `Rozdział III`, `Epilogue`, ...)         | none (title from the file name)         |
| `.html`, `.htm`, `.xhtml`                 | `HtmlReader`  | headings, else chapter-like paragraphs or big fonts                   | `<title>`, author `<meta>`, `lang`      |

Formats without a table of contents treat each heading as an entry, so text
before the first heading (title page, copyright) counts as front matter
missing from the table of contents and is skipped. Parts are named
`section-001`, ... (`pages 12-18` for PDFs) in the report.

### PDF

Only PDFs with a text layer can be read; scans raise `UnreadableBookError`
and need OCR first (for example with [ocrmypdf](https://ocrmypdf.readthedocs.io)).
The reader rebuilds the text from the page layout:

- running headers, footers and page numbers (lines in the top or bottom 10%
  of the page that repeat on several pages or are numbers) are dropped
- footnotes (small type below the text, starting with a marker) and
  superscript note markers are removed
- words hyphenated at line ends are joined, also across pages
- lines in a clearly bigger font become headings

`PdfReader(outline_depth=2)` splits at deeper outline levels; by default the
shallowest level with at least three entries is used. Multi-column layouts
are read row by row and may come out mixed.

### Plain text

The encoding is detected (UTF-8, CP1250, ISO-8859-2, ...). Paragraphs are
separated by blank lines or indentation, and lines wrapped at a fixed width
are joined. Project Gutenberg's licence header and footer are left out.

### Kindle

Only DRM-free files can be read; others raise `UnreadableBookError`.

### Choosing a reader yourself

```python
from anyaudiobook import AudiobookConverter, EdgeTTS
from anyaudiobook.readers import PdfReader

AudiobookConverter(
    "book.pdf",
    "out",
    EdgeTTS("en-US-BrianNeural"),
    reader=PdfReader(outline_depth=2, cover=False),
)
```

## Output

| `output_format` | Writer      | `output` is                                   | Result                                                                 |
| --------------- | ----------- | --------------------------------------------- | ---------------------------------------------------------------------- |
| `"mp3"`         | `Mp3Writer` | a directory                                   | `NN. Title.mp3` per chapter, ID3 tags: album, artist, title, track, cover |
| `"m4b"`         | `M4bWriter` | an `.m4b` file, or a directory for `<title>.m4b` | one AAC file with a chapter marker per chapter, tags and cover       |

M4B needs `ffmpeg`, checked before narration starts. Chapters are narrated
into a temporary directory and joined at the end; `M4bWriter(bitrate="96k")`
changes the AAC bitrate (64k by default).

Title, authors and cover come from the ebook; `metadata=BookMetadata(...)`
overrides any of them, and the file name is the title of last resort.
