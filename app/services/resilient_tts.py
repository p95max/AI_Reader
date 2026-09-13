"""Checkpointed TTS processing for retries and restart safety."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import UUID

from app.services.audio_chunk_store import AudioChunkStore
from app.services.audio_generation import (
    AudioChunkGenerator,
    GeneratedAudioChunk,
    audio_storage_key,
)
from app.services.storage import ObjectStorageError
from app.services.tts import SpeechSpeed, TTSError
from app.services.tts_usage import TTSUsageCostCalculator

logger = logging.getLogger(__name__)


class AudioChunkProcessingError(RuntimeError):
    """A retryable failure to generate one audio chunk."""


class ResilientTTSProcessor:
    """Generates only missing chunks and records every successful checkpoint."""

    def __init__(
        self,
        generator: AudioChunkGenerator,
        store: AudioChunkStore,
        *,
        cost_calculator: TTSUsageCostCalculator | None = None,
    ) -> None:
        self._generator = generator
        self._store = store
        self._cost_calculator = cost_calculator

    async def process(
        self,
        book_id: UUID,
        narration: str,
        *,
        voice: str,
        speed: SpeechSpeed,
        attempt_count: int,
    ) -> list[GeneratedAudioChunk]:
        await self._store.ensure_voice(book_id, voice)
        generated: list[GeneratedAudioChunk] = []
        for chunk_index, text in enumerate(self._generator.split_narration(narration)):
            if await self._store.is_ready(book_id, chunk_index):
                logger.info(
                    "tts_chunk_skipped_ready", extra={"book_id": str(book_id), "chunk": chunk_index}
                )
                continue

            started_at = perf_counter()
            try:
                chunk = self._generator.generate_chunk(
                    book_id,
                    chunk_index,
                    text,
                    voice=voice,
                    speed=speed,
                )
            except (ObjectStorageError, TTSError, ValueError) as error:
                await self._store.mark_failed(
                    book_id,
                    chunk_index=chunk_index,
                    narration=text,
                    storage_key=audio_storage_key(book_id, chunk_index),
                    voice=voice,
                    attempt_count=attempt_count,
                    error_message=str(error),
                )
                logger.exception(
                    "tts_chunk_generation_failed",
                    extra={
                        "book_id": str(book_id),
                        "chunk": chunk_index,
                        "attempt": attempt_count,
                    },
                )
                raise AudioChunkProcessingError(
                    f"Failed to generate TTS chunk {chunk_index} for book {book_id}"
                ) from error

            elapsed_ms = round((perf_counter() - started_at) * 1_000)
            tts_cost_usd = 0.0
            if self._cost_calculator is not None:
                usage = self._cost_calculator.calculate(
                    generated_audio_milliseconds=chunk.duration_milliseconds,
                    generation_time_milliseconds=elapsed_ms,
                )
                tts_cost_usd = usage.total_cost_usd
            await self._store.mark_ready(
                book_id,
                chunk,
                voice=voice,
                attempt_count=attempt_count,
                generation_time_milliseconds=elapsed_ms,
                tts_cost_usd=tts_cost_usd,
            )
            logger.info(
                "tts_chunk_generated",
                extra={
                    "book_id": str(book_id),
                    "chunk": chunk_index,
                    "duration_ms": chunk.duration_milliseconds,
                    "generation_ms": elapsed_ms,
                    "tts_cost_usd": tts_cost_usd,
                },
            )
            generated.append(chunk)
        return generated
