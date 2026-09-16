"""SQLAlchemy persistence for chapter and content-chunk records."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.chapter import Chapter, ContentChunk, ProcessingStatus
from app.services.documents.book_structure import StructuredChapter


class BookStructureStore(Protocol):
    async def replace(self, book_id: UUID, chapters: tuple[StructuredChapter, ...]) -> None: ...


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SQLAlchemyBookStructureStore:
    """Creates a book structure once, without invalidating completed audio."""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    async def replace(self, book_id: UUID, chapters: tuple[StructuredChapter, ...]) -> None:
        async with self._session_factory() as session:
            # Protect against concurrent/redelivered parser jobs.  The lock is
            # held only while the durable checkpoint is written, not while the
            # PDF is being parsed.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(CAST(:book_id AS text)))"),
                {"book_id": str(book_id)},
            )
            existing_chapter_id = await session.scalar(
                select(Chapter.id).where(Chapter.book_id == book_id).limit(1)
            )
            if existing_chapter_id is not None:
                await session.commit()
                return

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
