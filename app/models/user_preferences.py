from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserPreferences(Base):
    """Durable default narration choices for one user."""

    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    voice: Mapped[str] = mapped_column(String(100), default="Ryan")
    speed: Mapped[str] = mapped_column(String(20), default="normal")
    style: Mapped[str] = mapped_column(String(20), default="neutral")
    code_mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    table_mode: Mapped[str] = mapped_column(String(20), default="summarize")
    diagram_mode: Mapped[str] = mapped_column(String(20), default="describe")
    formula_mode: Mapped[str] = mapped_column(String(20), default="explain")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
