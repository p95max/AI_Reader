from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioChunkStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class AudioChunk(Base):
    """Durable metadata for one generated audio segment of a book."""

    __tablename__ = "audio_chunks"
    __table_args__ = (
        UniqueConstraint("book_id", "chunk_index", name="uq_audio_chunks_book_index"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    book_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    narration: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(100), default="audio/wav")
    duration_milliseconds: Mapped[int] = mapped_column(Integer)
    status: Mapped[AudioChunkStatus] = mapped_column(
        Enum(
            AudioChunkStatus,
            name="audio_chunk_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=AudioChunkStatus.PENDING,
    )
    voice: Mapped[str | None] = mapped_column(String(100))
    tts_provider: Mapped[str | None] = mapped_column(String(100))
    tts_model: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    generation_time_milliseconds: Mapped[int | None] = mapped_column(Integer)
    tts_cost_usd: Mapped[float] = mapped_column(Numeric(16, 8), default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
