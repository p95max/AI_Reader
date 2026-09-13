from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMUsageRecord(Base):
    """One durable provider response and the exact usage used for its cost calculation."""

    __tablename__ = "llm_usage_records"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    book_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        index=True,
    )
    chapter_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        index=True,
    )
    content_chunk_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("content_chunks.id", ondelete="CASCADE"),
        index=True,
    )
    provider_response_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    model_name: Mapped[str] = mapped_column(String(255), index=True)
    pricing_version: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    calculated_cost_usd: Mapped[float] = mapped_column(Numeric(16, 8), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
