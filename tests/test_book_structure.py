from uuid import UUID

import pytest

from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.services.documents.book_structure import BookStructureBuilder
from app.services.documents.book_structure_processor import BookStructureProcessor
from app.services.documents.pdf_parser import ParsedDocument, ParsedPage, TextBlock

BOOK_ID = UUID("12345678-1234-5678-1234-567812345678")


def block(page: int, text: str, *, heading: bool = False, code: bool = False) -> TextBlock:
    return TextBlock(
        page_number=page,
        text=text,
        bbox=(0, 0, 1, 1),
        font_size=20 if heading else 11,
        is_heading=heading,
        is_code=code,
    )


def page(number: int, *blocks: TextBlock) -> ParsedPage:
    return ParsedPage(
        number=number,
        text="\n".join(item.text for item in blocks),
        text_blocks=blocks,
        paragraphs=tuple(item for item in blocks if not item.is_heading and not item.is_code),
        headings=tuple(item for item in blocks if item.is_heading),
        code_blocks=tuple(item for item in blocks if item.is_code),
        tables=(),
        visuals=(),
        formulas=(),
    )


def test_builder_creates_chapters_and_ordered_content_chunks() -> None:
    document = ParsedDocument(
        page_count=2,
        pages=(
            page(1, block(1, "Глава 1", heading=True), block(1, "Первый текст.")),
            page(2, block(2, "Глава 2", heading=True), block(2, "print('code')", code=True)),
        ),
    )

    chapters = BookStructureBuilder().build(document)

    assert [(chapter.title, chapter.start_page, chapter.end_page) for chapter in chapters] == [
        ("Глава 1", 1, 1),
        ("Глава 2", 2, 2),
    ]
    assert chapters[0].chunks[0].source_text == "Первый текст."
    assert chapters[1].chunks[0].kind == "code"


def test_structure_records_start_in_the_durable_queue() -> None:
    chapter = Chapter(
        book_id=BOOK_ID,
        chapter_index=0,
        title="Глава",
        start_page=1,
        end_page=1,
        status=ProcessingStatus.QUEUED,
    )
    content = ContentChunk(
        chapter_id=BOOK_ID,
        chunk_index=0,
        page_number=1,
        kind="text",
        source_text="Текст.",
        status=ProcessingStatus.QUEUED,
    )

    assert chapter.status == content.status == ProcessingStatus.QUEUED


def test_builder_uses_one_fallback_chapter_when_pdf_has_no_headings() -> None:
    document = ParsedDocument(
        page_count=1,
        pages=(page(1, block(1, "Текст без заголовка.")),),
    )

    chapters = BookStructureBuilder().build(document)

    assert chapters[0].title == "Start of document"
    assert chapters[0].chunks[0].chunk_index == 0


def test_builder_ignores_standalone_page_numbers() -> None:
    document = ParsedDocument(
        page_count=2,
        pages=(
            page(1, block(1, "1"), block(1, "First actual paragraph.")),
            page(2, block(2, "Page 2"), block(2, "Second actual paragraph.")),
        ),
    )

    chapters = BookStructureBuilder().build(document)

    assert [chunk.source_text for chunk in chapters[0].chunks] == [
        "First actual paragraph.",
        "Second actual paragraph.",
    ]


def test_builder_drops_empty_cover_headings_and_malformed_text() -> None:
    document = ParsedDocument(
        page_count=1,
        pages=(
            page(
                1,
                block(1, "THE", heading=True),
                block(1, "TELL-TALE", heading=True),
                block(1, "HEART", heading=True),
                block(1, "\x03broken\x03", heading=True),
                block(1, "The first readable paragraph."),
            ),
        ),
    )

    chapters = BookStructureBuilder().build(document)

    assert len(chapters) == 1
    assert chapters[0].title == "THE TELL-TALE HEART"
    assert [chunk.source_text for chunk in chapters[0].chunks] == ["The first readable paragraph."]


def test_builder_splits_a_long_document_with_only_a_cover_title_into_sections() -> None:
    document = ParsedDocument(
        page_count=5,
        pages=tuple(
            page(
                number,
                *(
                    (block(number, "A LONG DOCUMENT", heading=True),)
                    if number == 1
                    else ()
                ),
                block(number, f"Readable text on page {number}."),
            )
            for number in range(1, 6)
        ),
    )

    chapters = BookStructureBuilder().build(document)

    assert [(chapter.title, chapter.start_page, chapter.end_page) for chapter in chapters] == [
        ("Section 1", 1, 2),
        ("Section 2", 3, 4),
        ("Section 3", 5, 5),
    ]
    assert [chunk.source_text for chunk in chapters[1].chunks] == [
        "Readable text on page 3.",
        "Readable text on page 4.",
    ]


class MemoryStore:
    def __init__(self) -> None:
        self.saved: tuple[UUID, object] | None = None

    async def replace(self, book_id: UUID, chapters: object) -> None:
        self.saved = (book_id, chapters)


@pytest.mark.asyncio
async def test_processor_persists_the_built_structure() -> None:
    document = ParsedDocument(
        page_count=1,
        pages=(page(1, block(1, "Глава", heading=True), block(1, "Текст.")),),
    )
    store = MemoryStore()
    book_id = UUID("12345678-1234-5678-1234-567812345678")

    chapters = await BookStructureProcessor(BookStructureBuilder(), store).create(book_id, document)  # type: ignore[arg-type]

    assert store.saved == (book_id, chapters)
