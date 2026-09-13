"""Durable LLM request accounting with aggregations for every ownership scope."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.book import Book
from app.models.chapter import Chapter, ContentChunk
from app.models.llm_usage import LLMUsageRecord

if TYPE_CHECKING:
    from app.services.ai_adapter import AIRequest, AIResponse


class UsageRecordStore(Protocol):
    async def record(self, request: AIRequest, response: AIResponse) -> None: ...


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class UsageTotals:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    cost_usd: float = 0.0


class SQLAlchemyUsageRecordStore:
    """Stores an immutable LLM result and calculates totals by any persisted scope."""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory

    async def record(self, request: AIRequest, response: AIResponse) -> None:
        if response.provider_response_id is None:
            return

        scope = request.usage_context
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(LLMUsageRecord.id).where(
                    LLMUsageRecord.provider_response_id == response.provider_response_id
                )
            )
            if existing is not None:
                return

            user_id, book_id, chapter_id, content_chunk_id = await self._resolve_scope(
                session, scope
            )
            session.add(
                LLMUsageRecord(
                    user_id=user_id,
                    book_id=book_id,
                    chapter_id=chapter_id,
                    content_chunk_id=content_chunk_id,
                    provider_response_id=response.provider_response_id,
                    model_name=response.model,
                    pricing_version=request.pricing_version,
                    input_tokens=response.usage.input_tokens,
                    cached_input_tokens=response.usage.cached_input_tokens,
                    output_tokens=response.usage.output_tokens,
                    calculated_cost_usd=response.cost.total_cost,
                )
            )
            await session.commit()

    async def totals(
        self,
        *,
        user_id: UUID | None = None,
        book_id: UUID | None = None,
        chapter_id: UUID | None = None,
        content_chunk_id: UUID | None = None,
    ) -> UsageTotals:
        """Aggregate usage for a user, book, chapter, or individual content chunk."""
        filters = (
            (LLMUsageRecord.user_id, user_id),
            (LLMUsageRecord.book_id, book_id),
            (LLMUsageRecord.chapter_id, chapter_id),
            (LLMUsageRecord.content_chunk_id, content_chunk_id),
        )
        if not any(value is not None for _, value in filters):
            raise ValueError("At least one usage scope must be provided")

        statement = select(
            func.coalesce(func.sum(LLMUsageRecord.input_tokens), 0),
            func.coalesce(func.sum(LLMUsageRecord.cached_input_tokens), 0),
            func.coalesce(func.sum(LLMUsageRecord.output_tokens), 0),
            func.count(LLMUsageRecord.id),
            func.coalesce(func.sum(LLMUsageRecord.calculated_cost_usd), 0),
        )
        for field, value in filters:
            if value is not None:
                statement = statement.where(field == value)

        async with self._session_factory() as session:
            row = (await session.execute(statement)).one()
        return UsageTotals(
            input_tokens=int(row[0]),
            cached_input_tokens=int(row[1]),
            output_tokens=int(row[2]),
            request_count=int(row[3]),
            cost_usd=float(row[4]),
        )

    @staticmethod
    async def _resolve_scope(
        session: AsyncSession,
        scope: object | None,
    ) -> tuple[UUID | None, UUID | None, UUID | None, UUID | None]:
        if scope is None:
            return None, None, None, None

        user_id = getattr(scope, "user_id", None)
        book_id = getattr(scope, "book_id", None)
        chapter_id = getattr(scope, "chapter_id", None)
        content_chunk_id = getattr(scope, "content_chunk_id", None)

        if content_chunk_id is not None:
            row = (
                (
                    await session.execute(
                        select(
                            Book.user_id.label("user_id"),
                            Book.id.label("book_id"),
                            Chapter.id.label("chapter_id"),
                            ContentChunk.id.label("content_chunk_id"),
                        )
                        .join(Chapter, ContentChunk.chapter_id == Chapter.id)
                        .join(Book, Chapter.book_id == Book.id)
                        .where(ContentChunk.id == content_chunk_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                return row["user_id"], row["book_id"], row["chapter_id"], row["content_chunk_id"]

        if chapter_id is not None:
            row = (
                (
                    await session.execute(
                        select(
                            Book.user_id.label("user_id"),
                            Book.id.label("book_id"),
                            Chapter.id.label("chapter_id"),
                        )
                        .join(Book, Chapter.book_id == Book.id)
                        .where(Chapter.id == chapter_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                return row["user_id"], row["book_id"], row["chapter_id"], None

        if book_id is not None:
            book = await session.get(Book, book_id)
            if book is not None:
                return book.user_id, book.id, None, None

        return user_id, book_id, chapter_id, content_chunk_id


class PersistentUsageReporter:
    """Async reporter used by the adapter to make usage persistence part of the request path."""

    def __init__(self, store: UsageRecordStore | None = None) -> None:
        self._store = store or SQLAlchemyUsageRecordStore()

    async def record(self, request: AIRequest, response: AIResponse) -> None:
        await self._store.record(request, response)
