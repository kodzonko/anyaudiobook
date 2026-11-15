"""Build and parse chapter audio file names."""

from anyaudiobook.models import BookContent, BookMetadata

MAX_TITLE_LENGTH = 150
"""Longest title kept in a file name, to stay under path length limits."""

_INVALID_CHARS = str.maketrans("", "", '\\/:*?"<>|')


def clean_title(title: str) -> str:
    """Strip characters Windows forbids in file names and cap the length.

    Args:
        title: The raw chapter title.

    Returns:
        A title safe to use as part of a file name.
    """
    cleaned = title.translate(_INVALID_CHARS).strip()
    if len(cleaned) > MAX_TITLE_LENGTH:
        cleaned = cleaned[: MAX_TITLE_LENGTH - 3] + "..."
    return cleaned


def book_filename(metadata: BookMetadata) -> str:
    """Return ``Author - Title`` for naming a book's audiobook file or folder.

    Whitespace (newlines included) is collapsed, characters file systems
    forbid are removed, and trailing dots and spaces, which Windows drops
    from names, are stripped. Without authors it is just the title.

    Args:
        metadata: The book's title and authors.

    Returns:
        A name safe for a file or folder, without an extension.
    """
    title = " ".join((metadata.title or "").split())
    author = " ".join(metadata.author.split())
    name = f"{author} - {title}" if author and title else author or title
    return clean_title(name).rstrip(". ") or "Audiobook"


def chapter_filename(
    chapter: BookContent, total_chapters: int, suffix: str = ".mp3"
) -> str:
    """Return the ``NN. Title.mp3`` file name for a chapter.

    The chapter number is zero-padded to the width of ``total_chapters`` so the
    files sort in order.

    Args:
        chapter: The chapter to name.
        total_chapters: How many chapters the book has.
        suffix: The audio file extension.

    Returns:
        The file name, without a directory.
    """
    width = len(str(total_chapters))
    return f"{chapter.chapter_number:0{width}d}. {clean_title(chapter.title)}{suffix}"


def parse_chapter_filename(stem: str) -> tuple[int, str]:
    """Split a ``NN. Title`` file stem into its track number and title.

    Args:
        stem: A file name without its extension, as made by :func:`chapter_filename`.

    Returns:
        A ``(track_number, chapter_title)`` pair.

    Raises:
        ValueError: If the stem does not start with a number followed by a dot.
    """
    number, separator, title = stem.partition(".")
    if not separator or not number.isdigit():
        raise ValueError(f"Not a numbered chapter file name: {stem!r}")
    return int(number), title.strip()
