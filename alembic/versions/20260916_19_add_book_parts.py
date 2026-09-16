"""Store continuation PDFs belonging to one logical book.

Revision ID: 20260916_19
Revises: 20260916_18
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "20260916_19"
down_revision = "20260916_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book_parts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("global_start_page", sa.Integer(), nullable=False),
        sa.Column("structure_built", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "sequence", name="uq_book_parts_sequence"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_book_parts_book_id", "book_parts", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_book_parts_book_id", table_name="book_parts")
    op.drop_table("book_parts")
