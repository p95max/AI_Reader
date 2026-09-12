"""Persistence for generated audio-chunk metadata."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.audio_chunk import AudioChunk
from app.services.audio_generation import GeneratedAudioChunk


class AudioChunkStore(Protocol):
    async def save_many(self, book_id: UUID, chunks: list[GeneratedAudioChunk]) -> None: ...


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SQLAlchemyAudioChunkStore:
    """Stores chunk order, narration, object key, and measured WAV duration."""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    async def save_many(self, book_id: UUID, chunks: list[GeneratedAudioChunk]) -> None:
        if not chunks:
            return
        records = [
            AudioChunk(
                book_id=book_id,
                chunk_index=chunk.chunk_index,
                narration=chunk.narration,
                storage_key=chunk.storage_key,
                content_type=chunk.content_type,
                duration_milliseconds=chunk.duration_milliseconds,
            )
            for chunk in chunks
        ]
        async with self._session_factory() as session:
            session.add_all(records)
            await session.commit()
