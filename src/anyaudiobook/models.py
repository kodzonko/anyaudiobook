"""Data models shared across the package."""

from pydantic import BaseModel


class BookContent(BaseModel):
    """A single chapter extracted from an ebook."""

    chapter_number: int
    title: str
    content: str
