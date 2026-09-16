"""Add display author to books.

Revision ID: 20260912_05
Revises: 20260912_04
Create Date: 2026-09-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_05"
down_revision: str | Sequence[str] | None = "20260912_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("author", sa.String(length=255), nullable=False, server_default="Unknown author"),
    )
    op.alter_column("books", "author", server_default=None)


def downgrade() -> None:
    op.drop_column("books", "author")
