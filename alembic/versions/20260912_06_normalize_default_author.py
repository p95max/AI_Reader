"""Normalize the default author name to English.

Revision ID: 20260912_06
Revises: 20260912_05
Create Date: 2026-09-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260912_06"
down_revision: str | Sequence[str] | None = "20260912_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE books SET author = 'Unknown author' WHERE author = ''")


def downgrade() -> None:
    op.execute("UPDATE books SET author = '' WHERE author = 'Unknown author'")
