from uuid import UUID

from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.services.books.book_progress import build_book_progress

BOOK_ID = UUID("12345678-1234-5678-1234-567812345678")
CHAPTER_ONE_ID = UUID("12345678-1234-5678-1234-567812345679")
CHAPTER_TWO_ID = UUID("12345678-1234-5678-1234-567812345680")


def chapter(id: UUID, index: int, *, status: ProcessingStatus = ProcessingStatus.QUEUED) -> Chapter:
    return Chapter(
        id=id,
        book_id=BOOK_ID,
        chapter_index=index,
        title=f"Глава {index + 1}",
        start_page=index + 1,
        end_page=index + 1,
        status=status,
    )


def chunk(
    id: UUID,
    chapter_id: UUID,
    index: int,
    status: ProcessingStatus,
) -> ContentChunk:
    return ContentChunk(
        id=id,
        chapter_id=chapter_id,
        chunk_index=index,
        page_number=index + 1,
        kind="text",
        source_text="Текст.",
        status=status,
    )


def test_progress_counts_book_chapters_and_chunks() -> None:
    first = chapter(CHAPTER_ONE_ID, 0)
    second = chapter(CHAPTER_TWO_ID, 1)
    result = build_book_progress(
        BOOK_ID,
        (first, second),
        (
            chunk(
                UUID("00000000-0000-0000-0000-000000000001"), first.id, 1, ProcessingStatus.READY
            ),
            chunk(
                UUID("00000000-0000-0000-0000-000000000002"), first.id, 0, ProcessingStatus.READY
            ),
            chunk(
                UUID("00000000-0000-0000-0000-000000000003"),
                second.id,
                0,
                ProcessingStatus.PROCESSING,
            ),
            chunk(
                UUID("00000000-0000-0000-0000-000000000004"), second.id, 1, ProcessingStatus.QUEUED
            ),
        ),
    )

    assert result.status == ProcessingStatus.PROCESSING
    assert result.progress_percent == 50.0
    assert (result.total_chapters, result.ready_chapters) == (2, 1)
    assert (result.total_chunks, result.ready_chunks, result.processing_chunks) == (4, 2, 1)
    assert result.queued_chunks == 1
    assert result.failed_chunks == 0
    assert result.chapters[0].status == ProcessingStatus.READY
    assert result.chapters[0].progress_percent == 100.0
    assert [item.chunk_index for item in result.chapters[0].chunks] == [0, 1]
    assert result.chapters[1].status == ProcessingStatus.PROCESSING
    assert result.chapters[1].progress_percent == 0.0


def test_failed_chunk_marks_chapter_and_book_as_failed() -> None:
    item = chapter(CHAPTER_ONE_ID, 0)
    result = build_book_progress(
        BOOK_ID,
        (item,),
        (chunk(UUID("00000000-0000-0000-0000-000000000005"), item.id, 0, ProcessingStatus.FAILED),),
    )

    assert result.status == ProcessingStatus.FAILED
    assert result.failed_chunks == 1
    assert result.chapters[0].status == ProcessingStatus.FAILED


def test_empty_chapter_keeps_its_persisted_status() -> None:
    item = chapter(CHAPTER_ONE_ID, 0, status=ProcessingStatus.PROCESSING)

    result = build_book_progress(BOOK_ID, (item,), ())

    assert result.status == ProcessingStatus.PROCESSING
    assert result.chapters[0].status == ProcessingStatus.PROCESSING
    assert result.progress_percent == 0.0
