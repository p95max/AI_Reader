"""Add page-range and pause state to books.

Revision ID: 20260916_18
Revises: 20260916_17
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "20260916_18"
down_revision = "20260916_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "books", sa.Column("page_count", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "books",
        sa.Column("processing_start_page", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "books", sa.Column("processing_end_page", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "books",
        sa.Column("processing_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE books
        SET page_count = COALESCE(
                (SELECT MAX(chapters.end_page) FROM chapters WHERE chapters.book_id = books.id),
                1
            ),
            processing_end_page = COALESCE(
                (SELECT MAX(chapters.end_page) FROM chapters WHERE chapters.book_id = books.id),
                1
            )
        """
    )


def downgrade() -> None:
    op.drop_column("books", "processing_paused")
    op.drop_column("books", "processing_end_page")
    op.drop_column("books", "processing_start_page")
    op.drop_column("books", "page_count")
