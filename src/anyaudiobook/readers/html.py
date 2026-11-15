"""Read single-file HTML books."""

from pathlib import Path

from anyaudiobook.readers.base import HtmlBookReader, HtmlSource


class HtmlReader(HtmlBookReader):
    """Reads a book saved as one HTML file.

    Title, author and language come from the document's ``<head>``; chapters
    from its headings (see :class:`HtmlBookReader`).
    """

    suffixes = (".html", ".htm", ".xhtml")

    def load(self, path: Path) -> HtmlSource:
        """Return the file's content; BeautifulSoup detects its encoding."""
        return HtmlSource(path.read_bytes())
