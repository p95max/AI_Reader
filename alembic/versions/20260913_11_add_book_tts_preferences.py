"""Persist speech preferences selected for each book.

Revision ID: 20260913_11
Revises: 20260913_10
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_11"
down_revision: str | Sequence[str] | None = "20260913_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("tts_voice", sa.String(length=100), server_default="Ryan", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("tts_speed", sa.String(length=20), server_default="normal", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("tts_style", sa.String(length=20), server_default="neutral", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("books", "tts_style")
    op.drop_column("books", "tts_speed")
    op.drop_column("books", "tts_voice")
