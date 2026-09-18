"""Checkpointed TTS processing for retries and restart safety."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import UUID

from app.services.audio.audio_chunk_store import AudioChunkStore
from app.services.audio.audio_generation import (
    AudioChunkGenerator,
    GeneratedAudioChunk,
    audio_storage_key,
)
from app.services.audio.tts import ReadingStyle, RetryableTTSError, SpeechSpeed, TTSError
from app.services.audio.tts_usage import TTSUsageCostCalculator
from app.services.infrastructure.storage import ObjectStorageError

logger = logging.getLogger(__name__)


class AudioChunkProcessingError(RuntimeError):
    """A retryable failure to generate one audio chunk."""


class TTSBudgetLimitExceeded(RuntimeError):
    """Raised before a provider request would exceed the book's TTS budget."""


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
        style: ReadingStyle = ReadingStyle.NEUTRAL,
        start_chunk_index: int = 0,
        max_tts_cost_usd: float = 0.0,
    ) -> list[GeneratedAudioChunk]:
        await self._store.ensure_voice(book_id, voice)
        generated: list[GeneratedAudioChunk] = []
        for offset, text in enumerate(self._generator.split_narration(narration)):
            chunk_index = start_chunk_index + offset
            if await self._store.is_ready(book_id, chunk_index):
                logger.info(
                    "tts_chunk_skipped_ready", extra={"book_id": str(book_id), "chunk": chunk_index}
                )
                continue

            if max_tts_cost_usd > 0 and self._cost_calculator is not None:
                estimated_cost = self._cost_calculator.estimate_text_cost(text)
                spent_cost = await self._store.ready_tts_cost_usd(book_id)
                if spent_cost + estimated_cost > max_tts_cost_usd:
                    logger.warning(
                        "tts_budget_limit_reached",
                        extra={
                            "book_id": str(book_id),
                            "chunk": chunk_index,
                            "spent_cost_usd": spent_cost,
                            "estimated_chunk_cost_usd": estimated_cost,
                            "max_cost_usd": max_tts_cost_usd,
                        },
                    )
                    raise TTSBudgetLimitExceeded(
                        f"TTS budget of ${max_tts_cost_usd:.2f} reached for book {book_id}"
                    )

            started_at = perf_counter()
            try:
                chunk = self._generator.generate_chunk(
                    book_id,
                    chunk_index,
                    text,
                    voice=voice,
                    speed=speed,
                    style=style,
                )
            except (ObjectStorageError, TTSError, ValueError) as error:
                await self._store.mark_failed(
                    book_id,
                    chunk_index=chunk_index,
                    narration=text,
                    storage_key=audio_storage_key(book_id, chunk_index),
                    voice=voice,
                    tts_provider=self._generator.tts_provider,
                    tts_model=self._generator.tts_model,
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
            try:
                await self._store.mark_ready(
                    book_id,
                    chunk,
                    voice=voice,
                    tts_provider=chunk.tts_provider,
                    tts_model=chunk.tts_model,
                    attempt_count=attempt_count,
                    generation_time_milliseconds=elapsed_ms,
                    tts_cost_usd=tts_cost_usd,
                )
            except Exception:
                # A deletion or database failure between upload and checkpoint
                # must not leave an object with no AudioChunk record.
                try:
                    self._generator.delete_chunk(chunk.storage_key)
                except ObjectStorageError:
                    logger.exception(
                        "tts_orphan_cleanup_failed",
                        extra={"book_id": str(book_id), "chunk": chunk_index},
                    )
                raise
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
