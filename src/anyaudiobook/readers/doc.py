"""Read legacy Word (DOC), RTF and OpenDocument files by converting them."""

import sys
import tempfile
from pathlib import Path

from anyaudiobook.errors import MissingToolError
from anyaudiobook.models import SourceBook
from anyaudiobook.readers.base import BookReader
from anyaudiobook.readers.docx import DocxReader
from anyaudiobook.readers.html import HtmlReader
from anyaudiobook.tools import find_tool, run_tool

LIBREOFFICE = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
)
"""Where LibreOffice is looked for, in order."""


class DocReader(BookReader):
    """Reads DOC, RTF and ODT files by converting them first.

    LibreOffice converts them to DOCX, keeping heading styles, which
    :class:`DocxReader` then reads. Without LibreOffice, macOS's built-in
    ``textutil`` converts them to HTML for :class:`HtmlReader`; headings are
    then found by font size and title patterns.
    """

    suffixes = (".doc", ".rtf", ".odt")

    def read(self, path: Path) -> SourceBook:
        """Convert the file and read the result.

        Raises:
            MissingToolError: If neither LibreOffice nor textutil is installed.
        """
        with tempfile.TemporaryDirectory(prefix="anyaudiobook-") as scratch:
            out_dir = Path(scratch)
            if soffice := find_tool(*LIBREOFFICE):
                run_tool(
                    [
                        soffice,
                        f"-env:UserInstallation={(out_dir / 'profile').as_uri()}",
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        str(out_dir),
                        str(path),
                    ],
                    f"Converting {path.name} with LibreOffice",
                )
                return DocxReader().read(out_dir / f"{path.stem}.docx")
            if sys.platform == "darwin" and (textutil := find_tool("textutil")):
                converted = out_dir / f"{path.stem}.html"
                run_tool(
                    [
                        textutil,
                        "-convert",
                        "html",
                        "-output",
                        str(converted),
                        str(path),
                    ],
                    f"Converting {path.name} with textutil",
                )
                return HtmlReader().read(converted)
        raise MissingToolError(
            f"Reading {path.suffix} files needs LibreOffice "
            "(https://www.libreoffice.org), which is not installed."
        )
