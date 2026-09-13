"""Cost comparison between the pre-processing estimate and recorded LLM usage."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        estimated = float(book.estimated_ai_cost_usd)
        actual = float(row[0])
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
        )
