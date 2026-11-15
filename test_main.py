import unittest
from unittest.mock import Mock, patch

import ebooklib

from main import EpubToAudiobookConverter


class ChunkEpubTests(unittest.TestCase):
    def test_content_and_heading_fallbacks(self):
        items = []
        for content in (
            b'<h1 title="7. Chapter Seven">Heading</h1><p>Text</p>',
            "<h1>Untitled heading</h1><p>Text</p>",
            "<p>No heading</p>",
            '<h1 title="invalid">Fallback title</h1><p>Text</p>',
        ):
            item = Mock()
            item.get_type.return_value = ebooklib.ITEM_DOCUMENT
            item.get_content.return_value = content
            item.get_name.return_value = "fallback.xhtml"
            items.append(item)

        converter = EpubToAudiobookConverter("book.epub", "output", "voice")
        with patch("main.epub.read_epub") as read_epub:
            read_epub.return_value.get_items.return_value = items
            converter.chunk_epub()

        self.assertEqual(
            [
                (chapter.chapter_number, chapter.title)
                for chapter in converter.chunked_content
            ],
            [
                (7, "Chapter Seven"),
                (2, "Untitled heading"),
                (3, "fallback.xhtml"),
                (4, "Fallback title"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
