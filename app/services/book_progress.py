"""Read-model for polling the processing progress of a book."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter, ContentChunk, ProcessingStatus


@dataclass(frozen=True, slots=True)
class ContentChunkProgress:
    id: UUID
    chunk_index: int
    page_number: int
    kind: str
    status: ProcessingStatus


@dataclass(frozen=True, slots=True)
class ChapterProgress:
    id: UUID
    chapter_index: int
    title: str
    start_page: int
    end_page: int
    status: ProcessingStatus
    total_chunks: int
    ready_chunks: int
    progress_percent: float
    chunks: tuple[ContentChunkProgress, ...]


@dataclass(frozen=True, slots=True)
class BookProgress:
    book_id: UUID
    status: ProcessingStatus
    total_chapters: int
    ready_chapters: int
    total_chunks: int
    queued_chunks: int
    processing_chunks: int
    ready_chunks: int
    failed_chunks: int
    progress_percent: float
    chapters: tuple[ChapterProgress, ...]


def _progress_percent(ready: int, total: int) -> float:
    return round((ready / total * 100) if total else 0, 2)


def _derive_status(
    statuses: tuple[ProcessingStatus, ...],
    *,
    fallback: ProcessingStatus = ProcessingStatus.QUEUED,
) -> ProcessingStatus:
    """Reduce item statuses so that errors and active work remain visible."""
    if not statuses:
        return fallback
    if ProcessingStatus.FAILED in statuses:
        return ProcessingStatus.FAILED
    if ProcessingStatus.PROCESSING in statuses:
        return ProcessingStatus.PROCESSING
    if all(status == ProcessingStatus.READY for status in statuses):
        return ProcessingStatus.READY
    return ProcessingStatus.QUEUED


def build_book_progress(
    book_id: UUID,
    chapters: tuple[Chapter, ...],
    chunks: tuple[ContentChunk, ...],
) -> BookProgress:
    """Build one consistent, ordered progress snapshot from persisted records."""
    chunks_by_chapter: dict[UUID, list[ContentChunk]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_chapter[chunk.chapter_id].append(chunk)

    chapter_progress = tuple(
        _build_chapter_progress(chapter, tuple(chunks_by_chapter[chapter.id]))
        for chapter in chapters
    )
    all_chunk_statuses = tuple(chunk.status for chunk in chunks)
    return BookProgress(
        book_id=book_id,
        status=_derive_status(tuple(chapter.status for chapter in chapter_progress)),
        total_chapters=len(chapter_progress),
        ready_chapters=sum(
            chapter.status == ProcessingStatus.READY for chapter in chapter_progress
        ),
        total_chunks=len(chunks),
        queued_chunks=all_chunk_statuses.count(ProcessingStatus.QUEUED),
        processing_chunks=all_chunk_statuses.count(ProcessingStatus.PROCESSING),
        ready_chunks=all_chunk_statuses.count(ProcessingStatus.READY),
        failed_chunks=all_chunk_statuses.count(ProcessingStatus.FAILED),
        progress_percent=_progress_percent(
            all_chunk_statuses.count(ProcessingStatus.READY), len(chunks)
        ),
        chapters=chapter_progress,
    )


def _build_chapter_progress(chapter: Chapter, chunks: tuple[ContentChunk, ...]) -> ChapterProgress:
    ordered_chunks = tuple(sorted(chunks, key=lambda chunk: chunk.chunk_index))
    chunk_progress = tuple(
        ContentChunkProgress(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            kind=chunk.kind,
            status=chunk.status,
        )
        for chunk in ordered_chunks
    )
    statuses = tuple(chunk.status for chunk in ordered_chunks)
    ready_chunks = statuses.count(ProcessingStatus.READY)
    return ChapterProgress(
        id=chapter.id,
        chapter_index=chapter.chapter_index,
        title=chapter.title,
        start_page=chapter.start_page,
        end_page=chapter.end_page,
        status=_derive_status(statuses, fallback=chapter.status),
        total_chunks=len(chunk_progress),
        ready_chunks=ready_chunks,
        progress_percent=_progress_percent(ready_chunks, len(chunk_progress)),
        chunks=chunk_progress,
    )


class BookProgressService:
    """Loads the data required by the book progress polling endpoint."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, book_id: UUID) -> BookProgress:
        chapters = tuple(
            (
                await self._session.scalars(
                    select(Chapter)
                    .where(Chapter.book_id == book_id)
                    .order_by(Chapter.chapter_index)
                )
            ).all()
        )
        chunks = tuple(
            (
                await self._session.scalars(
                    select(ContentChunk)
                    .join(Chapter, ContentChunk.chapter_id == Chapter.id)
                    .where(Chapter.book_id == book_id)
                    .order_by(Chapter.chapter_index, ContentChunk.chunk_index)
                )
            ).all()
        )
        return build_book_progress(book_id, chapters, chunks)
