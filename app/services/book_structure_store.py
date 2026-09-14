"""SQLAlchemy persistence for chapter and content-chunk records."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.audio_chunk import AudioChunk
from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.services.book_structure import StructuredChapter


class BookStructureStore(Protocol):
    async def replace(self, book_id: UUID, chapters: tuple[StructuredChapter, ...]) -> None: ...


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SQLAlchemyBookStructureStore:
    """Atomically replaces a book's structure and creates its durable queued work."""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    async def replace(self, book_id: UUID, chapters: tuple[StructuredChapter, ...]) -> None:
        async with self._session_factory() as session:
            chapter_ids = select(Chapter.id).where(Chapter.book_id == book_id)
            # A fresh parse invalidates every earlier narration/audio segment.
            await session.execute(delete(AudioChunk).where(AudioChunk.book_id == book_id))
            await session.execute(
                delete(ContentChunk).where(ContentChunk.chapter_id.in_(chapter_ids))
            )
            await session.execute(delete(Chapter).where(Chapter.book_id == book_id))

            for structured_chapter in chapters:
                chapter = Chapter(
                    book_id=book_id,
                    chapter_index=structured_chapter.chapter_index,
                    title=structured_chapter.title,
                    start_page=structured_chapter.start_page,
                    end_page=structured_chapter.end_page,
                    status=ProcessingStatus.QUEUED,
                )
                session.add(chapter)
                await session.flush()
                session.add_all(
                    [
                        ContentChunk(
                            chapter_id=chapter.id,
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            kind=chunk.kind,
                            source_text=chunk.source_text,
                            status=ProcessingStatus.QUEUED,
                        )
                        for chunk in structured_chapter.chunks
                    ]
                )
            await session.commit()
