from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._util import ID3NoHeaderError
from mutagen.id3._frames import APIC


def add_metadata(
    mp3_file: str | Path,
    author: str,
    book_title: str,
    chapter_title: str,
    cover_image: str | Path | None = None,
) -> None:
    """
    Add metadata to an MP3 file.

    Args:
        mp3_file (str|Path): Path to the MP3 file
        author (str): Author name to add as the artist
        book_title (str): Book title to add as the album
        chapter_title (str): Chapter title to add as the track title
        cover_image (str|Path|None): Path to cover image file to add as album art

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

    if cover_image:
        # We need to use ID3 directly to add cover art
        id3 = ID3(file_path)
        with open(str(cover_image), "rb") as img_file:
            img_data = img_file.read()

        mime_type = "image/jpeg"
        if str(cover_image).lower().endswith(".png"):
            mime_type = "image/png"

        id3.add(
            APIC(
                encoding=3,  # UTF-8
                mime=mime_type,
                type=3,  # 3 is for cover image
                desc="Cover",
                data=img_data,
            )
        )
        id3.save()


if __name__ == "__main__":

    for mp3_file in Path("output").rglob("*.mp3"):
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
            "the-big-book-of-science-fiction-b-iext120009289.jpg",
        )
