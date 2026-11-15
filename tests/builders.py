"""Build real ebook and audio files for tests: DOCX, PDF and silent MP3."""

import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import ClassVar

from reportlab.lib.pagesizes import A5
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from anyaudiobook.tts import TextProgress

# --- MP3 ---------------------------------------------------------------------

_FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0xC0])
"""MPEG-1 Layer III, 128 kbit/s, 44.1 kHz, mono, no CRC."""
_FRAME_BYTES = 417
_FRAME_SECONDS = 1152 / 44100


def silent_mp3(seconds: float) -> bytes:
    """Return a valid MP3 stream of silence lasting about ``seconds``."""
    frames = max(1, round(seconds / _FRAME_SECONDS))
    frame = _FRAME_HEADER + bytes(_FRAME_BYTES - len(_FRAME_HEADER))
    return frame * frames


@dataclass
class FakeEngine:
    """A speech engine writing silent MP3s whose length follows the text.

    Every 100 characters last a second, so chapter boundaries in an M4B
    can be checked.
    """

    audio_suffix: ClassVar[str] = ".mp3"
    texts: list[str] = field(default_factory=list)

    @staticmethod
    def seconds(text: str) -> float:
        """Return how long the audio for ``text`` lasts."""
        return 0.5 + len(text) / 100

    async def synthesize(
        self, text: str, output_path: Path, progress: TextProgress | None = None
    ) -> None:
        """Write silence for ``text`` to ``output_path``, reporting halfway."""
        self.texts.append(text)
        if progress is not None:
            progress(len(text) // 2)
        output_path.write_bytes(silent_mp3(self.seconds(text)))


# --- DOCX --------------------------------------------------------------------

_W = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)
_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_TYPES = "application/vnd.openxmlformats-officedocument.wordprocessingml"


@dataclass(frozen=True)
class Para:
    """One paragraph of a test DOCX."""

    text: str
    style: str | None = None
    """``Title``, ``Heading1``, ``Heading2`` or None for body text."""
    footnote: str | None = None
    """Text of a footnote referenced at the end of the paragraph."""


def write_docx(
    path: Path,
    paragraphs: Sequence[Para],
    *,
    title: str | None = "Test Document",
    author: str | None = "Jane Doe",
) -> Path:
    """Write a minimal but valid DOCX with styles, footnotes and core properties."""
    notes: list[str] = []
    body: list[str] = []
    for para in paragraphs:
        style = f'<w:pPr><w:pStyle w:val="{para.style}"/></w:pPr>' if para.style else ""
        reference = ""
        if para.footnote:
            notes.append(para.footnote)
            reference = (
                '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                f'<w:footnoteReference w:id="{len(notes)}"/></w:r>'
            )
        body.append(
            f'<w:p>{style}<w:r><w:t xml:space="preserve">{escape(para.text)}'
            f"</w:t></w:r>{reference}</w:p>"
        )
    styles = "".join(
        f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/></w:style>'
        for style_id, name in (
            ("Title", "Title"),
            ("Heading1", "heading 1"),
            ("Heading2", "heading 2"),
        )
    )
    footnotes = "".join(
        f'<w:footnote w:id="{number}"><w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p></w:footnote>'
        for number, text in enumerate(notes, start=1)
    )
    core = "".join(
        f"<{tag}>{escape(value)}</{tag}>"
        for tag, value in (("dc:title", title), ("dc:creator", author))
        if value
    )
    files = {
        "[Content_Types].xml": (
            f'{_XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{_TYPES}.document.main+xml"/>'
            f'<Override PartName="/word/styles.xml" ContentType="{_TYPES}.styles+xml"/>'
            f'<Override PartName="/word/footnotes.xml" ContentType="{_TYPES}.footnotes+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'{_XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/'
            'relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": (
            f'{_XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/styles" Target="styles.xml"/>'
            f'<Relationship Id="rId2" Type="{_REL}/footnotes" Target="footnotes.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": f"{_XML}<w:document {_W}><w:body>{''.join(body)}</w:body></w:document>",
        "word/styles.xml": f"{_XML}<w:styles {_W}>{styles}</w:styles>",
        "word/footnotes.xml": f"{_XML}<w:footnotes {_W}>{footnotes}</w:footnotes>",
        "docProps/core.xml": (
            f'{_XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/'
            '2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"{core}</cp:coreProperties>"
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


# --- PDF ---------------------------------------------------------------------


@dataclass(frozen=True)
class PdfChapter:
    """One chapter of a test PDF; every chapter starts on a new page.

    Paragraphs given as a string are wrapped to the page width; given as a
    list of strings, they are drawn one line per string, so tests can place
    hyphenated line ends. A word ending in ``^1`` gets a superscript note
    marker.
    """

    heading: str | None
    paragraphs: Sequence[str | Sequence[str]] = ()
    footnote: str | None = None
    """Text drawn in small type at the bottom of the chapter's first page."""
    in_outline: bool = True


_PAGE_WIDTH, _PAGE_HEIGHT = A5
_LEFT = 40
_TOP = _PAGE_HEIGHT - 70
_BOTTOM = 70
_BODY = 10
_LEADING = 13
_INDENT = 14


def write_pdf(
    path: Path,
    chapters: Sequence[PdfChapter],
    *,
    title: str = "Test PDF",
    author: str = "Jane Doe",
    running_header: str = "Test PDF",
    outline: bool = True,
) -> Path:
    """Write a text PDF with headers, page numbers and optionally an outline."""
    pdf = canvas.Canvas(str(path), pagesize=A5)
    pdf.setTitle(title)
    pdf.setAuthor(author)
    state = {"page": 0, "y": 0.0}

    def new_page() -> None:
        if state["page"]:
            pdf.showPage()
        state["page"] += 1
        pdf.setFont("Helvetica", 8)
        pdf.drawString(_LEFT, _PAGE_HEIGHT - 25, running_header)
        pdf.drawCentredString(_PAGE_WIDTH / 2, 20, str(state["page"]))
        state["y"] = _TOP

    def draw_line(text: str, x: float) -> None:
        if state["y"] < _BOTTOM:
            new_page()
        line = pdf.beginText(x, state["y"])
        for word in text.split(" "):
            word, marker, note = word.partition("^")
            line.setFont("Helvetica", _BODY)
            line.textOut(word)
            if marker:
                line.setFont("Helvetica", 6)
                line.setRise(4)
                line.textOut(note)
                line.setRise(0)
            line.setFont("Helvetica", _BODY)
            line.textOut(" ")
        pdf.drawText(line)
        state["y"] -= _LEADING

    for number, chapter in enumerate(chapters):
        new_page()
        if chapter.heading:
            key = f"chapter-{number}"
            pdf.bookmarkPage(key, fit="XYZ", top=state["y"] + 20)
            if outline and chapter.in_outline:
                pdf.addOutlineEntry(chapter.heading, key, level=0)
            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawString(_LEFT, state["y"], chapter.heading)
            state["y"] -= 36
        if chapter.footnote:
            pdf.setFont("Helvetica", 7)
            pdf.drawString(_LEFT, _BOTTOM - 25, chapter.footnote)
        for paragraph in chapter.paragraphs:
            lines = (
                simpleSplit(
                    paragraph, "Helvetica", _BODY, _PAGE_WIDTH - 2 * _LEFT - _INDENT
                )
                if isinstance(paragraph, str)
                else list(paragraph)
            )
            for index, text in enumerate(lines):
                draw_line(text, _LEFT + (_INDENT if index == 0 else 0))
    pdf.save()
    return path


def write_image_pdf(path: Path, pages: int = 2) -> Path:
    """Write a PDF of drawings without any text, like a scan."""
    pdf = canvas.Canvas(str(path), pagesize=A5)
    for _ in range(pages):
        pdf.rect(40, 40, 200, 300, fill=1)
        pdf.showPage()
    pdf.save()
    return path
