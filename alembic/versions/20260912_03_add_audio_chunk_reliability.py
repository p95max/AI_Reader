"""Add TTS reliability metadata to audio chunks.

Revision ID: 20260912_03
Revises: 20260912_02
Create Date: 2026-09-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260912_03"
down_revision: str | Sequence[str] | None = "20260912_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    chunk_status = postgresql.ENUM(
        "pending", "ready", "failed", name="audio_chunk_status", create_type=False
    )
    chunk_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "audio_chunks",
        sa.Column("status", chunk_status, nullable=False, server_default="ready"),
    )
    op.add_column("audio_chunks", sa.Column("voice", sa.String(length=100), nullable=True))
    op.add_column(
        "audio_chunks",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "audio_chunks",
        sa.Column("generation_time_milliseconds", sa.Integer(), nullable=True),
    )
    op.add_column("audio_chunks", sa.Column("error_message", sa.Text(), nullable=True))
    op.alter_column("audio_chunks", "status", server_default=None)
    op.alter_column("audio_chunks", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_column("audio_chunks", "error_message")
    op.drop_column("audio_chunks", "generation_time_milliseconds")
    op.drop_column("audio_chunks", "attempt_count")
    op.drop_column("audio_chunks", "voice")
    op.drop_column("audio_chunks", "status")
    postgresql.ENUM(name="audio_chunk_status").drop(op.get_bind(), checkfirst=True)
