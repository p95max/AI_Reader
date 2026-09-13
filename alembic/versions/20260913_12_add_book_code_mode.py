"""Persist the selected technical-code narration mode per book.

Revision ID: 20260913_12
Revises: 20260913_11
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_12"
down_revision: str | Sequence[str] | None = "20260913_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("code_mode", sa.String(length=20), server_default="hybrid", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("books", "code_mode")
