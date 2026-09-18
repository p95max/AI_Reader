"""Aggregate recorded AI and TTS usage for the settings dashboard."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_chunk import AudioChunk, AudioChunkStatus
from app.models.book import Book, BookStatus
from app.models.llm_usage import LLMUsageRecord


@dataclass(frozen=True, slots=True)
class BookUsageSummaryItem:
    id: UUID
    title: str
    status: BookStatus
    created_at: datetime
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    request_count: int
    ai_cost_usd: float
    tts_cost_usd: float
    total_cost_usd: float
    generated_audio_seconds: int


@dataclass(frozen=True, slots=True)
class UsageSummary:
    total_books: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    request_count: int
    ai_cost_usd: float
    tts_cost_usd: float
    total_cost_usd: float
    generated_audio_seconds: int
    books: tuple[BookUsageSummaryItem, ...]


class UsageSummaryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> UsageSummary:
        llm_usage = (
            select(
                LLMUsageRecord.book_id.label("book_id"),
                func.coalesce(func.sum(LLMUsageRecord.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsageRecord.cached_input_tokens), 0).label(
                    "cached_input_tokens"
                ),
                func.coalesce(func.sum(LLMUsageRecord.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMUsageRecord.calculated_cost_usd), 0).label("ai_cost_usd"),
                func.count(LLMUsageRecord.id).label("request_count"),
            )
            .group_by(LLMUsageRecord.book_id)
            .subquery()
        )
        tts_usage = (
            select(
                AudioChunk.book_id.label("book_id"),
                func.coalesce(func.sum(AudioChunk.tts_cost_usd), 0).label("tts_cost_usd"),
                func.coalesce(func.sum(AudioChunk.duration_milliseconds), 0).label(
                    "audio_milliseconds"
                ),
            )
            .where(AudioChunk.status == AudioChunkStatus.READY)
            .group_by(AudioChunk.book_id)
            .subquery()
        )
        rows = (
            await self._session.execute(
                select(
                    Book.id,
                    Book.title,
                    Book.status,
                    Book.created_at,
                    llm_usage.c.input_tokens,
                    llm_usage.c.cached_input_tokens,
                    llm_usage.c.output_tokens,
                    llm_usage.c.ai_cost_usd,
                    llm_usage.c.request_count,
                    tts_usage.c.tts_cost_usd,
                    tts_usage.c.audio_milliseconds,
                )
                .outerjoin(llm_usage, llm_usage.c.book_id == Book.id)
                .outerjoin(tts_usage, tts_usage.c.book_id == Book.id)
                .where(Book.user_id == user_id)
                .order_by(Book.created_at.desc())
            )
        ).all()

        books = tuple(
            BookUsageSummaryItem(
                id=row.id,
                title=row.title,
                status=row.status,
                created_at=row.created_at,
                input_tokens=int(row.input_tokens or 0),
                cached_input_tokens=int(row.cached_input_tokens or 0),
                output_tokens=int(row.output_tokens or 0),
                request_count=int(row.request_count or 0),
                ai_cost_usd=float(row.ai_cost_usd or 0),
                tts_cost_usd=float(row.tts_cost_usd or 0),
                total_cost_usd=round(float(row.ai_cost_usd or 0) + float(row.tts_cost_usd or 0), 8),
                generated_audio_seconds=round(int(row.audio_milliseconds or 0) / 1_000),
            )
            for row in rows
        )
        return UsageSummary(
            total_books=len(books),
            input_tokens=sum(book.input_tokens for book in books),
            cached_input_tokens=sum(book.cached_input_tokens for book in books),
            output_tokens=sum(book.output_tokens for book in books),
            request_count=sum(book.request_count for book in books),
            ai_cost_usd=round(sum(book.ai_cost_usd for book in books), 8),
            tts_cost_usd=round(sum(book.tts_cost_usd for book in books), 8),
            total_cost_usd=round(sum(book.total_cost_usd for book in books), 8),
            generated_audio_seconds=sum(book.generated_audio_seconds for book in books),
            books=books,
        )
