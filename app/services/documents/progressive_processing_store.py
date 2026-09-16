"""Database snapshot used by the progressive-processing planner."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.audio_chunk import AudioChunk, AudioChunkStatus
from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.services.documents.progressive_processing import PendingContentChunk

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SQLAlchemyProgressiveProcessingStore:
    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    async def pending_chunks(self, book_id: UUID) -> tuple[PendingContentChunk, ...]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(ContentChunk.id, Chapter.chapter_index, ContentChunk.chunk_index)
                .join(Chapter, ContentChunk.chapter_id == Chapter.id)
                .where(
                    Chapter.book_id == book_id,
                    ContentChunk.status == ProcessingStatus.QUEUED,
                )
                .order_by(Chapter.chapter_index, ContentChunk.chunk_index)
            )
        return tuple(PendingContentChunk(*row) for row in rows.tuples())

    async def ready_audio_duration_milliseconds(self, book_id: UUID) -> int:
        async with self._session_factory() as session:
            duration = await session.scalar(
                select(func.coalesce(func.sum(AudioChunk.duration_milliseconds), 0)).where(
                    AudioChunk.book_id == book_id,
                    AudioChunk.status == AudioChunkStatus.READY,
                )
            )
        return int(duration or 0)
