# Skipping front and back matter

Ebooks contain a lot that nobody wants read aloud: tables of contents,
copyright pages, indexes, endnotes, "also by" pages, footnote markers in the
middle of sentences. ANYaudiobook classifies every part ("document") of the
book and narrates only the main text, unless you configure it otherwise.

Documents are an EPUB's spine documents; other formats are split into
documents by their table of contents or headings first (see
[formats.md](formats.md)), so the same rules apply to every format. Signals
specific to EPUB markup (guide, landmarks, `linear="no"`) simply never fire
for formats that lack them.

The code lives in `src/anyaudiobook/matter/` (classification),
`src/anyaudiobook/markup.py` (clean-up inside chapters) and
`src/anyaudiobook/selection.py` (applying the options).

## Check before you narrate

Narration takes a long time, so look at what will be read first: set
`DRY_RUN = True` in `main.py` to print the report and stop.

```text
 #  action   kind           words  title                   file               reason
 1  skip     empty              0  cover.xhtml             cover.xhtml        no text
 2  skip     copyright        294  Copyright               copyright.xhtml    7 copyright and imprint markers
 3  skip     unlisted          71  epigraph.xhtml          epigraph.xhtml     before the main text and missing from the table of contents
 4  narrate  body            1647  Chapter 1. Beginnings   ch01.xhtml         main text
...
41  skip     index           4419  Index                   index.xhtml        336 lines look like index entries
Narrating 32 of 43 documents (233,716 words), skipping 11.
```

Every row says why the document was kept or skipped, so a wrong call is easy
to spot and override (see [Configuration](#configuration)).

## How documents are classified

Documents are read in reading order (for EPUB, the spine order the book
declares). Signals are checked from most to least reliable.

| Strength | Signal                                                                                                                                                                                                                        | Applies                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Decisive | No text at all (cover images, image-only pages)                                                                                                                                                                               | anywhere                                                         |
| Decisive | The EPUB 3 navigation document                                                                                                                                                                                                | anywhere                                                         |
| Decisive | `epub:type` / `role` markup (`toc`, `copyright-page`, `endnotes`, `doc-acknowledgments`, ...) on elements holding most of the page's text                                                                                     | anywhere                                                         |
| Decisive | EPUB 2 guide and EPUB 3 landmark entries pointing at the whole page                                                                                                                                                           | anywhere                                                         |
| Decisive | Content shape: copyright/imprint pages, index entries (`term, 12, 45`), tables of contents (mostly links, or lines ending in rising page numbers), notes (paragraphs linking back into chapters), book lists dense with ISBNs | anywhere                                                         |
| Title    | Heading or TOC label, in Polish or English (`Podziękowania`, `Spis treści`, `Also by…`, `Opinie o…`)                                                                                                                          | outside the main text; inside it only for pages under 1500 words |
| Weak     | File name words (`copyright.xhtml`, `przypisy.xhtml`), guide entries pointing inside the page, pages under 30 words                                                                                                           | outside the main text only                                       |
| Weak     | Missing from the table of contents                                                                                                                                                                                            | before the main text only                                        |

Markup saying a page is a chapter, prologue, foreword, epilogue and so on
always wins, and keeps the page.

**The main text** runs from the first to the last document that no signal
objects to. When the book's table of contents lists most of those documents,
the main text starts at the first listed one. A `bodymatter` landmark or
`text` guide entry, when present, marks the start instead. This position
check is what lets a short "Part Two" page between chapters stay, while a
short dedication before the first chapter goes.

Pages the spine marks `linear="no"` are always skipped. A book with no clear
main text ignores the weak signals, so they can never remove everything.

### Kinds

`body` is narrated; everything else is skipped by default:

`empty` (never narrated), `cover`, `title-page`, `toc`, `copyright`,
`dedication`, `epigraph`, `editorial-note` (publisher's, editor's or
translator's note), `acknowledgments`, `notes`, `index`, `bibliography`,
`glossary`, `list-of-figures`, `reference` (family trees, chronologies, maps,
character lists), `about-author`, `advertisement`, `short-page`, `unlisted`,
`auxiliary` (`linear="no"`).

## Clean-up inside chapters

Narrated chapters also lose:

- note reference markers: `epub:type="noteref"`, `role="doc-noteref"`,
  `<sup>1</sup>`, `[1]`, `*` links. A superscript straight after a digit that
  is not a link (`10<sup>6</sup>`) is kept as an exponent.
- inline footnotes and endnotes, marked up semantically or with common class
  names (`footnote`, `przypis`, ...)
- page-break markers and `<nav>` blocks
- `<head>` content such as `<title>`, which ebook tools often fill with the
  book title
- in PDFs: running headers, footers, page numbers and footnotes in small type
  at the bottom of the page (see [formats.md](formats.md#pdf))
- optionally tables (`drop_tables`) and figure/table captions
  (`drop_captions`)

Text keeps one line per paragraph, heading and list item, so the narrator
pauses between them, for example after the chapter title.

## Configuration

`FilterOptions`, set as `FILTER` in `main.py`:

| Option             | Default                                | Meaning                                                                                              |
| ------------------ | -------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `skip`             | `DEFAULT_SKIP` (every kind but `body`) | Kinds not to narrate                                                                                 |
| `include`          | `()`                                   | Regexes, matched ignoring case against file name and title; matches are narrated whatever their kind |
| `exclude`          | `()`                                   | Regexes; matches are never narrated. Wins over `include`                                             |
| `short_page_words` | `30`                                   | Below this, a page outside the main text counts as a short page                                      |
| `long_page_words`  | `1500`                                 | From this length, a page inside the main text is kept despite a front/back matter title              |
| `drop_tables`      | `False`                                | Leave tables out                                                                                     |
| `drop_captions`    | `False`                                | Leave captions out                                                                                   |

```python
from anyaudiobook.matter.models import MatterKind

FILTER = FilterOptions(
    skip=DEFAULT_SKIP - {MatterKind.DEDICATION, MatterKind.ACKNOWLEDGMENTS},
    include=(r"^Od tłumacza$",),
    exclude=(r"front matter",),
)
```

Keyword lists (titles, file names, markup types) are in
`src/anyaudiobook/matter/keywords.py`. Add phrases for other languages there.

## Known limitations

- Each document is judged as a whole. Converters that merge sections into
  one file (for example a PDF-converted book whose "Table of Contents" file
  also holds the Preface, or a single "front matter" file with preface,
  acknowledgments and about-the-author) are kept or skipped together. Use
  `include`/`exclude` for those.
- Title and file name keywords, and the chapter titles recognised in
  formats without headings, cover Polish and English.
