"""Cost comparison between the pre-processing estimate and recorded LLM usage."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_chunk import AudioChunk, AudioChunkStatus
from app.models.book import Book
from app.models.llm_usage import LLMUsageRecord


@dataclass(frozen=True)
class BookCostComparison:
    estimated_cost_usd: float
    actual_cost_usd: float
    difference_usd: float
    actual_input_tokens: int
    actual_cached_input_tokens: int
    actual_output_tokens: int
    request_count: int
    estimate_model_name: str
    estimate_pricing_version: str
    actual_tts_cost_usd: float
    generated_audio_seconds: int
    tts_generation_seconds: int
    total_processing_cost_usd: float


class BookCostService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, book_id: UUID) -> BookCostComparison:
        book = await self._session.get(Book, book_id)
        if book is None:
            raise LookupError("Book was not found")
        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(LLMUsageRecord.calculated_cost_usd), 0),
                    func.coalesce(func.sum(LLMUsageRecord.input_tokens), 0),
                    func.coalesce(func.sum(LLMUsageRecord.cached_input_tokens), 0),
                    func.coalesce(func.sum(LLMUsageRecord.output_tokens), 0),
                    func.count(LLMUsageRecord.id),
                ).where(LLMUsageRecord.book_id == book_id)
            )
        ).one()
        tts_row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(AudioChunk.tts_cost_usd), 0),
                    func.coalesce(func.sum(AudioChunk.duration_milliseconds), 0),
                    func.coalesce(func.sum(AudioChunk.generation_time_milliseconds), 0),
                ).where(
                    AudioChunk.book_id == book_id,
                    AudioChunk.status == AudioChunkStatus.READY,
                )
            )
        ).one()
        estimated = float(book.estimated_ai_cost_usd)
        actual = float(row[0])
        actual_tts = float(tts_row[0])
        return BookCostComparison(
            estimated_cost_usd=estimated,
            actual_cost_usd=actual,
            difference_usd=round(actual - estimated, 8),
            actual_input_tokens=int(row[1]),
            actual_cached_input_tokens=int(row[2]),
            actual_output_tokens=int(row[3]),
            request_count=int(row[4]),
            estimate_model_name=book.estimate_model_name,
            estimate_pricing_version=book.estimate_pricing_version,
            actual_tts_cost_usd=actual_tts,
            generated_audio_seconds=round(int(tts_row[1]) / 1_000),
            tts_generation_seconds=round(int(tts_row[2]) / 1_000),
            total_processing_cost_usd=round(actual + actual_tts, 8),
        )
