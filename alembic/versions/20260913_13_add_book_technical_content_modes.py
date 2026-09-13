"""Persist technical-content narration modes per book.

Revision ID: 20260913_13
Revises: 20260913_12
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_13"
down_revision: str | Sequence[str] | None = "20260913_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("table_mode", sa.String(length=20), server_default="summarize", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("diagram_mode", sa.String(length=20), server_default="describe", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("formula_mode", sa.String(length=20), server_default="explain", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("books", "formula_mode")
    op.drop_column("books", "diagram_mode")
    op.drop_column("books", "table_mode")
