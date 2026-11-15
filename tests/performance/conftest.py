"""Fixtures for the performance tests."""

import pytest

from tests.performance.books import Shelf


@pytest.fixture(scope="session")
def shelf(tmp_path_factory: pytest.TempPathFactory) -> Shelf:
    """Generated books, written once per session as tests ask for them."""
    return Shelf(tmp_path_factory.mktemp("books"))
