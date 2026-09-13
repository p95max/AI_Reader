"""Create user ownership and durable LLM usage tracking.

Revision ID: 20260913_08
Revises: 20260913_07
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260913_08"
down_revision: str | Sequence[str] | None = "20260913_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.execute(
        sa.text(
            f"INSERT INTO users (id, email) VALUES ('{LOCAL_USER_ID}', 'local@ai-reader.invalid')"
        )
    )

    op.add_column("books", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(sa.text(f"UPDATE books SET user_id = '{LOCAL_USER_ID}' WHERE user_id IS NULL"))
    op.alter_column("books", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_books_user_id_users", "books", "users", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_books_user_id", "books", ["user_id"])

    op.create_table(
        "llm_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("pricing_version", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("cached_input_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("calculated_cost_usd", sa.Numeric(16, 8), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_chunk_id"], ["content_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_response_id"),
    )
    for column in (
        "user_id",
        "book_id",
        "chapter_id",
        "content_chunk_id",
        "model_name",
        "created_at",
    ):
        op.create_index(f"ix_llm_usage_records_{column}", "llm_usage_records", [column])


def downgrade() -> None:
    op.drop_table("llm_usage_records")
    op.drop_index("ix_books_user_id", table_name="books")
    op.drop_constraint("fk_books_user_id_users", "books", type_="foreignkey")
    op.drop_column("books", "user_id")
    op.drop_table("users")
