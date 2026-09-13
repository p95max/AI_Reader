"""Record the actual TTS cost of each generated audio chunk.

Revision ID: 20260913_10
Revises: 20260913_09
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_10"
down_revision: str | Sequence[str] | None = "20260913_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audio_chunks",
        sa.Column("tts_cost_usd", sa.Numeric(16, 8), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("audio_chunks", "tts_cost_usd")
