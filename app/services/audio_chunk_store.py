"""Persistence for generated audio-chunk metadata."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.audio_chunk import AudioChunk, AudioChunkStatus
from app.services.audio_generation import GeneratedAudioChunk


class AudioChunkStore(Protocol):
    async def save_many(self, book_id: UUID, chunks: list[GeneratedAudioChunk]) -> None: ...

    async def is_ready(self, book_id: UUID, chunk_index: int) -> bool: ...

    async def ensure_voice(self, book_id: UUID, voice: str) -> None: ...

    async def mark_ready(
        self,
        book_id: UUID,
        chunk: GeneratedAudioChunk,
        *,
        voice: str,
        attempt_count: int,
        generation_time_milliseconds: int,
    ) -> None: ...

    async def mark_failed(
        self,
        book_id: UUID,
        *,
        chunk_index: int,
        narration: str,
        storage_key: str,
        voice: str,
        attempt_count: int,
        error_message: str,
    ) -> None: ...


class VoiceMismatchError(RuntimeError):
    """Raised before a book would receive chunks generated with another voice."""


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

    async def is_ready(self, book_id: UUID, chunk_index: int) -> bool:
        async with self._session_factory() as session:
            status = await session.scalar(
                select(AudioChunk.status).where(
                    AudioChunk.book_id == book_id,
                    AudioChunk.chunk_index == chunk_index,
                )
            )
        return status == AudioChunkStatus.READY

    async def ensure_voice(self, book_id: UUID, voice: str) -> None:
        async with self._session_factory() as session:
            stored_voice = await session.scalar(
                select(AudioChunk.voice)
                .where(AudioChunk.book_id == book_id, AudioChunk.voice.is_not(None))
                .limit(1)
            )
        if stored_voice is not None and stored_voice != voice:
            raise VoiceMismatchError(
                f"Book {book_id} already has audio generated with voice '{stored_voice}'"
            )

    async def mark_ready(
        self,
        book_id: UUID,
        chunk: GeneratedAudioChunk,
        *,
        voice: str,
        attempt_count: int,
        generation_time_milliseconds: int,
    ) -> None:
        async with self._session_factory() as session:
            record = await self._get_chunk(session, book_id, chunk.chunk_index)
            if record is None:
                session.add(
                    AudioChunk(
                        book_id=book_id,
                        chunk_index=chunk.chunk_index,
                        narration=chunk.narration,
                        storage_key=chunk.storage_key,
                        content_type=chunk.content_type,
                        duration_milliseconds=chunk.duration_milliseconds,
                        status=AudioChunkStatus.READY,
                        voice=voice,
                        attempt_count=attempt_count,
                        generation_time_milliseconds=generation_time_milliseconds,
                    )
                )
            else:
                record.narration = chunk.narration
                record.storage_key = chunk.storage_key
                record.content_type = chunk.content_type
                record.duration_milliseconds = chunk.duration_milliseconds
                record.status = AudioChunkStatus.READY
                record.voice = voice
                record.attempt_count = attempt_count
                record.generation_time_milliseconds = generation_time_milliseconds
                record.error_message = None
            await session.commit()

    async def mark_failed(
        self,
        book_id: UUID,
        *,
        chunk_index: int,
        narration: str,
        storage_key: str,
        voice: str,
        attempt_count: int,
        error_message: str,
    ) -> None:
        async with self._session_factory() as session:
            record = await self._get_chunk(session, book_id, chunk_index)
            if record is None:
                session.add(
                    AudioChunk(
                        book_id=book_id,
                        chunk_index=chunk_index,
                        narration=narration,
                        storage_key=storage_key,
                        content_type="audio/wav",
                        duration_milliseconds=0,
                        status=AudioChunkStatus.FAILED,
                        voice=voice,
                        attempt_count=attempt_count,
                        error_message=error_message[:2_000],
                    )
                )
            else:
                record.status = AudioChunkStatus.FAILED
                record.voice = voice
                record.attempt_count = attempt_count
                record.error_message = error_message[:2_000]
            await session.commit()

    @staticmethod
    async def _get_chunk(
        session: AsyncSession,
        book_id: UUID,
        chunk_index: int,
    ) -> AudioChunk | None:
        return await session.scalar(
            select(AudioChunk).where(
                AudioChunk.book_id == book_id,
                AudioChunk.chunk_index == chunk_index,
            )
        )
