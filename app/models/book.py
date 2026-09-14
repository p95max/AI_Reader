from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BookStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(
        String(255), default="Unknown author", server_default="Unknown author"
    )
    publication_year: Mapped[int | None] = mapped_column(nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    estimated_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_ai_cost_usd: Mapped[float] = mapped_column(Numeric(16, 8), default=0)
    estimate_model_name: Mapped[str] = mapped_column(String(255), default="")
    estimate_pricing_version: Mapped[str] = mapped_column(String(100), default="default")
    tts_voice: Mapped[str] = mapped_column(String(100), default="alloy")
    tts_speed: Mapped[str] = mapped_column(String(20), default="normal")
    tts_style: Mapped[str] = mapped_column(String(20), default="neutral")
    code_mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    table_mode: Mapped[str] = mapped_column(String(20), default="summarize")
    diagram_mode: Mapped[str] = mapped_column(String(20), default="describe")
    formula_mode: Mapped[str] = mapped_column(String(20), default="explain")
    status: Mapped[BookStatus] = mapped_column(
        Enum(
            BookStatus,
            name="book_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=BookStatus.UPLOADED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
