import asyncio
import warnings
from pathlib import Path

import ebooklib
import edge_tts
from bs4 import BeautifulSoup
from ebooklib import epub
from edge_tts.typing import Voice
from pydantic import BaseModel

# Silence specific ebooklib warnings
warnings.filterwarnings(
    "ignore",
    message="In the future version we will turn default option ignore_ncx to True.",
)
warnings.filterwarnings(
    "ignore",
    message="This search incorrectly ignores the root element, and will be fixed in a future version.",
)


async def get_available_voices() -> list[Voice]:
    """Get a list of available voices in this TTS engine"""
    return await edge_tts.list_voices()


class BookContent(BaseModel):
    """Model to store the content of a book chapter"""

    chapter_number: int
    title: str
    content: str


class EpubToAudiobookConverter:
    """Convert an epub file to an audiobook using TTS"""

    def __init__(
        self, epub_path: str, output_dir: str | Path, voice: str, pitch: str = "+0Hz"
    ) -> None:
        self.epub_path = epub_path
        self.audiobook_path = Path(output_dir)
        self.chunked_content: list[BookContent] = []
        self.voice = voice
        self.pitch = pitch

    def _is_title_case(self, text: str) -> bool:
        """Check if text is in title case (each major word starts with uppercase)"""
        # Skip single word or empty titles
        if not text or len(text.split()) <= 1:
            return False

        return text != text.upper()

    def _make_output_path(self, book_content: BookContent) -> Path:
        """Calculate padding digits based on total number of chapters"""
        total_chapters = len(self.chunked_content)
        padding_length = len(str(total_chapters))

        # Format the chapter number with dynamic padding
        padded_number = f"{book_content.chapter_number:0{padding_length}d}"

        # Clean the title to make it suitable for Windows filenames
        # Remove characters that are invalid in Windows filenames: \ / : * ? " < > |
        clean_title = (
            book_content.title.replace("\\", "")
            .replace("/", "")
            .replace(":", "")
            .replace("*", "")
        )
        clean_title = (
            clean_title.replace("?", "")
            .replace('"', "")
            .replace("<", "")
            .replace(">", "")
            .replace("|", "")
        )

        # Trim whitespace and limit length to avoid path too long errors
        clean_title = clean_title.strip()
        if len(clean_title) > 150:
            clean_title = clean_title[:147] + "..."

        return self.audiobook_path / f"{padded_number}. {clean_title}.mp3"

    def _ensure_output_dir(self) -> None:
        """Ensure the output directory exists"""
        self.audiobook_path.mkdir(parents=True, exist_ok=True)

    def _skip_fluff(self, title: str) -> bool:
        """Skip chapters that are fluff like intro or about authors"""
        return title not in [
            "Text/dedykacja.xhtml",
            "Podziękowania",
            "Drzewo genealogiczne",
            "Chronologia",
            "",
            "Spis treści:",
        ]

    async def _generate_voice_for_chapter(self, book_content: BookContent) -> None:
        communicate = edge_tts.Communicate(
            book_content.content, self.voice, pitch=self.pitch
        )
        output_path = str(self._make_output_path(book_content).absolute())
        await communicate.save(output_path)
        print(
            f"Saved: {book_content.chapter_number}/{len(self.chunked_content)} \033[31m{book_content.title}\033[0m in \033[90m{output_path}\033[0m"
        )

    async def _generate_all_chapters(self, number_of_concurrent_tasks: int) -> None:
        # Create a semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(number_of_concurrent_tasks)

        async def _process_chapter(chapter: BookContent) -> None:
            async with semaphore:
                print(
                    f"Processing chapter: {chapter.chapter_number}/{len(self.chunked_content)} \033[31m{chapter.title}\033[0m"
                )
                await self._generate_voice_for_chapter(chapter)

        tasks = [_process_chapter(chapter) for chapter in self.chunked_content]
        await asyncio.gather(*tasks)

    def generate_audiobook(self, number_of_concurrent_tasks: int = 10) -> None:
        """Generate the audiobook from the chunked content"""
        self._ensure_output_dir()
        asyncio.run(self._generate_all_chapters(number_of_concurrent_tasks))

    def chunk_epub(self) -> None:
        """Split the epub into chapters"""
        book = epub.read_epub(self.epub_path)
        fallback_chapter_number = 1
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode("utf-8")
                soup = BeautifulSoup(html_content, "html.parser")
                title = item.get_name()  # Default fallback title
                heading_tag = soup.find(["h1"])
                if heading_tag:
                    # Check if heading has a title attribute (which contains the full title with chapter number)
                    if heading_tag.has_attr("title"):
                        try:
                            title = (
                                heading_tag["title"]
                                .split(". ")[1]
                                .replace("„", "")
                                .replace("”", "")
                                .strip()
                            )
                        except IndexError:
                            title = heading_tag.get_text().strip()
                    else:
                        # If no title attribute, use the text content of the h1 element
                        title = heading_tag.get_text().strip()

                        # Check if this is a chapter heading with an ID that contains "toc"
                        is_chapter_heading = (
                            heading_tag.has_attr("id")
                            and "toc" in heading_tag["id"].lower()
                        )

                        # Only apply the "About" prefix if it's not a chapter heading and is in title case
                        # if not is_chapter_heading and self._is_title_case(title):
                        #     title = f"About {title}"

                for element in soup(["script", "style"]):
                    element.decompose()

                text = soup.get_text().strip()

                try:
                    chapter_number = int(heading_tag["title"].split(". ")[0])
                except (KeyError, TypeError, ValueError):
                    chapter_number = fallback_chapter_number

                if text and self._skip_fluff(title):
                    self.chunked_content.append(
                        BookContent(
                            chapter_number=chapter_number,
                            title=title,
                            content=text,
                        )
                    )
                    fallback_chapter_number += 1


if __name__ == "__main__":
    book = EpubToAudiobookConverter(
        r"C:\Users\username\path\to\ebook.epub",
        r"C:\Users\username\path\to\output_dir",
        "pl-PL-ZofiaNeural",
        "-10Hz",
    )
    book.chunk_epub()

    book.generate_audiobook(5)
