"""Regenerate the Kindle test books ``book.mobi`` (MOBI 7) and ``book.azw3``.

Needs Calibre's ``ebook-convert``. Run from the repository root::

    uv run python tests/fixtures/make_kindle_fixtures.py
"""

import io
import subprocess
import tempfile
from pathlib import Path

from ebooklib import epub
from PIL import Image

HERE = Path(__file__).parent
WORDS = " ".join(["The story goes on."] * 60)

PAGES = [
    (
        "copyright.xhtml",
        "Copyright",
        (
            "<h1>Copyright</h1><p>© 2020 Jane Doe. All rights reserved. "
            "ISBN 978-0-00-000000-0. Published by Test Press.</p>"
        ),
    ),
    (
        "ch1.xhtml",
        "Chapter 1. Beginnings",
        f"<h1>Chapter 1. Beginnings</h1><p>{WORDS}</p>",
    ),
    ("ch2.xhtml", "Chapter 2. Endings", f"<h1>Chapter 2. Endings</h1><p>{WORDS}</p>"),
    (
        "ack.xhtml",
        "Acknowledgments",
        "<h1>Acknowledgments</h1><p>Thanks to everyone who helped.</p>",
    ),
]


def build_epub(path: Path) -> None:
    """Write the source EPUB with a cover image."""
    book = epub.EpubBook()
    book.set_identifier("kindle-fixture")
    book.set_title("Kindle Test Book")
    book.set_language("en")
    book.add_author("Jane Doe")
    cover = io.BytesIO()
    Image.new("RGB", (60, 90), (200, 40, 40)).save(cover, "JPEG")
    book.set_cover("cover.jpg", cover.getvalue(), create_page=False)
    items = []
    for name, title, body in PAGES:
        item = epub.EpubHtml(title=title, file_name=name, lang="en")
        item.content = f"<html><body>{body}</body></html>"
        book.add_item(item)
        items.append(item)
    book.toc = [
        epub.Link(item.file_name, title, f"toc-{n}")
        for n, (item, (_, title, _)) in enumerate(zip(items, PAGES, strict=True))
    ]
    book.spine = items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)


def main() -> None:
    """Build the EPUB and convert it to both Kindle formats."""
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "book.epub"
        build_epub(source)
        for target, extra in (
            ("book.mobi", ["--mobi-file-type", "old"]),
            ("book.azw3", []),
        ):
            subprocess.run(
                ["ebook-convert", str(source), str(HERE / target), *extra],
                check=True,
                capture_output=True,
            )


if __name__ == "__main__":
    main()
