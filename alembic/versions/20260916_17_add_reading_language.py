"""Store the narration language selected for a book and user defaults.

Revision ID: 20260916_17
Revises: 20260914_16
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "20260916_17"
down_revision = "20260914_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("reading_language", sa.String(length=12), nullable=False, server_default="auto"),
    )
    op.add_column(
        "user_preferences",
        sa.Column("reading_language", sa.String(length=12), nullable=False, server_default="auto"),
    )
    op.alter_column("books", "reading_language", server_default=None)
    op.alter_column("user_preferences", "reading_language", server_default=None)


def downgrade() -> None:
    op.drop_column("user_preferences", "reading_language")
    op.drop_column("books", "reading_language")
