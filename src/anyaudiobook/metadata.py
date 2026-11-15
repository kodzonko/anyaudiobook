"""Write ID3 tags and cover art to chapter MP3 files."""

from pathlib import Path

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC
from mutagen.id3._util import ID3NoHeaderError

from anyaudiobook.filenames import parse_chapter_filename
from anyaudiobook.models import CoverImage


def add_metadata(
    mp3_file: str | Path,
    author: str,
    book_title: str,
    chapter_title: str,
    track_number: int,
    cover_image: str | Path | CoverImage | None = None,
) -> None:
    """Tag an MP3 file with book and chapter details.

    Args:
        mp3_file: Path to the MP3 file.
        author: Author name, stored as the artist.
        book_title: Book title, stored as the album.
        chapter_title: Chapter title, stored as the track title.
        track_number: Track number.
        cover_image: Optional JPEG or PNG image (or file) to embed as album art.
    """
    file_path = str(mp3_file)

    try:
        audio = EasyID3(file_path)
    except ID3NoHeaderError:
        ID3().save(file_path)
        audio = EasyID3(file_path)

    audio["artist"] = author
    audio["album"] = book_title
    audio["title"] = chapter_title
    audio["tracknumber"] = str(track_number)
    audio.save()

    if cover_image:
        cover = (
            cover_image
            if isinstance(cover_image, CoverImage)
            else CoverImage.from_file(cover_image)
        )
        id3 = ID3(file_path)
        id3.setall(
            "APIC",
            [
                APIC(
                    encoding=3,  # UTF-8
                    mime=cover.mime_type,
                    type=3,  # front cover
                    desc="Cover",
                    data=cover.data,
                )
            ],
        )
        id3.save()


def tag_chapters(
    audio_dir: str | Path,
    author: str,
    book_title: str,
    cover_image: str | Path | CoverImage | None = None,
) -> None:
    """Tag every ``NN. Title.mp3`` file under a directory.

    The track number and chapter title come from each file name.

    Args:
        audio_dir: Directory searched recursively for MP3 files.
        author: Author name, stored as the artist.
        book_title: Book title, stored as the album.
        cover_image: Optional JPEG or PNG file to embed as album art.

    Raises:
        ValueError: If an MP3 file name does not start with a track number.
    """
    for mp3_file in sorted(Path(audio_dir).rglob("*.mp3")):
        track_number, chapter_title = parse_chapter_filename(mp3_file.stem)
        add_metadata(
            mp3_file, author, book_title, chapter_title, track_number, cover_image
        )
