"""Persist each book's pre-processing cost estimate.

Revision ID: 20260913_09
Revises: 20260913_08
Create Date: 2026-09-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260913_09"
down_revision: str | Sequence[str] | None = "20260913_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "books",
        sa.Column("estimated_input_tokens", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("estimated_output_tokens", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("estimated_ai_cost_usd", sa.Numeric(16, 8), server_default="0", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("estimate_model_name", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column(
            "estimate_pricing_version",
            sa.String(length=100),
            server_default="default",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("books", "estimate_pricing_version")
    op.drop_column("books", "estimate_model_name")
    op.drop_column("books", "estimated_ai_cost_usd")
    op.drop_column("books", "estimated_output_tokens")
    op.drop_column("books", "estimated_input_tokens")
