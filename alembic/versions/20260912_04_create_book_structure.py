"""Create chapter and content chunk tables.

Revision ID: 20260912_04
Revises: 20260912_03
Create Date: 2026-09-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260912_04"
down_revision: str | Sequence[str] | None = "20260912_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    processing_status = postgresql.ENUM(
        "queued", "processing", "ready", "failed", name="processing_status", create_type=False
    )
    processing_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column("status", processing_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", "chapter_index", name="uq_chapters_book_index"),
    )
    op.create_index("ix_chapters_book_id", "chapters", ["book_id"])
    op.create_table(
        "content_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("status", processing_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_id", "chunk_index", name="uq_content_chunks_chapter_index"),
    )
    op.create_index("ix_content_chunks_chapter_id", "content_chunks", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_content_chunks_chapter_id", table_name="content_chunks")
    op.drop_table("content_chunks")
    op.drop_index("ix_chapters_book_id", table_name="chapters")
    op.drop_table("chapters")
    postgresql.ENUM(name="processing_status").drop(op.get_bind(), checkfirst=True)
