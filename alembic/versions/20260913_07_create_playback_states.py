"""Create durable playback state for each book.

Revision ID: 20260913_07
Revises: 20260912_06
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260913_07"
down_revision: str | Sequence[str] | None = "20260912_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playback_states",
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audio_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("position_milliseconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["audio_chunk_id"], ["audio_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("book_id"),
    )


def downgrade() -> None:
    op.drop_table("playback_states")
