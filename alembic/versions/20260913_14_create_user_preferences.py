"""Create durable user narration preferences.

Revision ID: 20260913_14
Revises: 20260913_13
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260913_14"
down_revision: str | Sequence[str] | None = "20260913_13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voice", sa.String(length=100), server_default="Ryan", nullable=False),
        sa.Column("speed", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("style", sa.String(length=20), server_default="neutral", nullable=False),
        sa.Column("code_mode", sa.String(length=20), server_default="hybrid", nullable=False),
        sa.Column("table_mode", sa.String(length=20), server_default="summarize", nullable=False),
        sa.Column("diagram_mode", sa.String(length=20), server_default="describe", nullable=False),
        sa.Column("formula_mode", sa.String(length=20), server_default="explain", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
