"""Create audio chunks table.

Revision ID: 20260912_02
Revises: 20260907_01
Create Date: 2026-09-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260912_02"
down_revision: str | Sequence[str] | None = "20260907_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("duration_milliseconds", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "duration_milliseconds >= 0", name="ck_audio_chunks_duration_nonnegative"
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "chunk_index", name="uq_audio_chunks_book_index"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_audio_chunks_book_id", "audio_chunks", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_audio_chunks_book_id", table_name="audio_chunks")
    op.drop_table("audio_chunks")
