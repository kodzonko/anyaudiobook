"""How long reading a book takes, per input format and book size.

Reading is the first step of every conversion and what the TUI waits for
before showing its preview: :func:`read_book` reads the file with the reader
for its format, then chooses the chapters, which is shared by all formats
and also timed on its own.
"""

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from anyaudiobook.readers import read_source
from anyaudiobook.selection import read_book, select_chapters
from tests.performance.books import INPUT_FORMATS, SIZES, BookSpec, Shelf

pytestmark = pytest.mark.performance

_SIZE_IDS = [spec.name for spec in SIZES]


def _group(benchmark: BenchmarkFixture, spec: BookSpec) -> None:
    """Compare all ways of reading a book of the same size with each other."""
    benchmark.group = f"read {spec.name} ({spec.words:,} words)"
    benchmark.extra_info["words"] = spec.words


@pytest.mark.parametrize("spec", SIZES, ids=_SIZE_IDS)
@pytest.mark.parametrize(
    "extension", INPUT_FORMATS, ids=[e.lstrip(".") for e in INPUT_FORMATS]
)
def test_read_book(
    benchmark: BenchmarkFixture, shelf: Shelf, extension: str, spec: BookSpec
) -> None:
    """Read a generated book from a file and choose its chapters."""
    path = shelf.book(spec, extension)
    _group(benchmark, spec)

    book = benchmark(read_book, path)

    assert [chapter.title for chapter in book.chapters] == spec.chapter_titles


@pytest.mark.parametrize("spec", SIZES, ids=_SIZE_IDS)
def test_select_chapters(
    benchmark: BenchmarkFixture, shelf: Shelf, spec: BookSpec
) -> None:
    """Choose the chapters of a book already read, as every format does.

    Shows how much of reading is the shared front and back matter
    classification rather than the format's reader.
    """
    source = read_source(shelf.book(spec, ".epub"))
    _group(benchmark, spec)

    book = benchmark(select_chapters, source)

    assert [chapter.title for chapter in book.chapters] == spec.chapter_titles
