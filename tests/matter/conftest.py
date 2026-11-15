"""Fixtures for the front and back matter tests."""

from collections.abc import Callable
from typing import Any

import pytest

from anyaudiobook.models import Document

DocumentFactory = Callable[..., Document]

LONG_TEXT = " ".join(["word"] * 2000)
"""Text long enough to count as a real chapter for every threshold."""


@pytest.fixture
def make_document() -> DocumentFactory:
    """Return a factory building a :class:`Document` from body HTML.

    Keyword arguments go to :meth:`Document.from_html`.
    """

    def factory(
        body: str = f"<p>{LONG_TEXT}</p>",
        file_name: str = "Text/ch.xhtml",
        **kwargs: Any,
    ) -> Document:
        html = f"<html><body>{body}</body></html>"
        return Document.from_html(file_name, html, **kwargs)

    return factory
