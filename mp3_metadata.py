from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._util import ID3NoHeaderError


def add_metadata(
    mp3_file: str | Path, author: str, book_title: str, chapter_title: str
) -> None:
    """
    Add metadata to an MP3 file.

    Args:
        mp3_file (str|Path): Path to the MP3 file
        author (str): Author name to add as the artist
        book_title (str): Book title to add as the album
        chapter_title (str): Chapter title to add as the track title

    Returns:
        None
    """
    # Convert to string path
    file_path = str(mp3_file)

    try:
        # Try to load existing ID3 tags
        audio = EasyID3(file_path)
    except ID3NoHeaderError:
        audio = ID3()
        audio.save(file_path)
        audio = EasyID3(file_path)

    # Add metadata
    audio["artist"] = author
    audio["album"] = book_title
    audio["title"] = chapter_title
    audio.save()


if __name__ == "__main__":

    for mp3_file in Path("a/output").rglob("*.mp3"):
        file_stem = mp3_file.stem
        # Remove leading numbers followed by a dot (like "004.")
        chapter_title = file_stem
        if file_stem and file_stem[0].isdigit():
            chapter_title = "".join(file_stem.split(".", 1)[1:]).strip()
        add_metadata(
            mp3_file,
            "Jeff VanderMeer",
            "The Big Book of Science Fiction",
            chapter_title,
        )
