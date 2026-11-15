"""High-level ebook to audiobook conversion."""

from pathlib import Path

from anyaudiobook.matter import Decision, FilterOptions
from anyaudiobook.models import BookContent, BookMetadata
from anyaudiobook.readers import BookReader
from anyaudiobook.report import format_report
from anyaudiobook.selection import ParsedBook, read_book
from anyaudiobook.tts import SpeechEngine
from anyaudiobook.writers import AudiobookWriter, writer_for


class AudiobookConverter:
    """Convert an ebook of any supported format into an audiobook.

    One object runs the whole pipeline, each step replaceable:

    1. **read** the ebook with the :class:`BookReader` for its extension,
    2. **select** the chapters, skipping front and back matter as
       :class:`FilterOptions` say,
    3. **narrate** them with a :class:`SpeechEngine`,
    4. **package** the audio with the :class:`AudiobookWriter` of the output
       format (one MP3 per chapter, or one M4B with chapter markers).

    Example::

        converter = AudiobookConverter(
            "book.pdf", "out", EdgeTTS("en-US-BrianNeural"), output_format="m4b"
        )
        print(converter.report())
        converter.convert()
    """

    def __init__(
        self,
        source: str | Path,
        output: str | Path,
        engine: SpeechEngine,
        *,
        output_format: str | AudiobookWriter = "mp3",
        filter_options: FilterOptions | None = None,
        reader: BookReader | None = None,
        metadata: BookMetadata | None = None,
    ) -> None:
        """Set up a conversion.

        Args:
            source: The ebook file.
            output: Where to write: a directory for MP3 chapters; an
                ``.m4b`` file, or a directory to put one in, for M4B.
            engine: The speech engine, e.g. ``EdgeTTS("en-US-BrianNeural")``.
            output_format: A registered format name (``mp3``, ``m4b``) or a
                configured writer such as ``M4bWriter(bitrate="96k")``.
            filter_options: What to narrate; defaults to :class:`FilterOptions`.
            reader: The reader to use; chosen by file extension when None.
            metadata: Title, authors and cover overriding what the ebook
                says about itself; unset fields keep the ebook's values.

        Raises:
            UnsupportedFormatError: If ``output_format`` is not registered.
        """
        self.source = Path(source)
        self.output = Path(output)
        self.engine = engine
        self.writer = (
            writer_for(output_format)
            if isinstance(output_format, str)
            else output_format
        )
        self.filter_options = filter_options or FilterOptions()
        self.reader = reader
        self.metadata_overrides = metadata
        self._book: ParsedBook | None = None

    def read(self) -> ParsedBook:
        """Read the ebook and choose the chapters to narrate.

        Called by the other methods when needed; call it yourself to read
        again after changing :attr:`filter_options`.
        """
        self._book = read_book(self.source, self.filter_options, self.reader)
        return self._book

    @property
    def book(self) -> ParsedBook:
        """The ebook as read by :meth:`read`."""
        return self._book or self.read()

    @property
    def chapters(self) -> list[BookContent]:
        """The chapters that will be narrated."""
        return self.book.chapters

    @property
    def decisions(self) -> list[Decision]:
        """What is narrated or skipped, and why: one entry per document."""
        return self.book.decisions

    @property
    def metadata(self) -> BookMetadata:
        """The metadata the audio is tagged with.

        The user's overrides win over the ebook's own metadata, which wins
        over the file name as the title.
        """
        return (
            BookMetadata(title=self.source.stem)
            .updated(self.book.metadata)
            .updated(self.metadata_overrides)
        )

    def report(self) -> str:
        """Return a table of what will be narrated and skipped, and why."""
        return format_report(self.decisions)

    def convert(self, concurrency: int = 10) -> list[Path]:
        """Narrate the chapters and write the audiobook.

        Args:
            concurrency: Most chapters narrated at the same time.

        Returns:
            The files written.
        """
        return self.writer.write(
            self.chapters, self.metadata, self.output, self.engine, concurrency
        )
