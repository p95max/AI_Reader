"""Store a publication year when a PDF provides explicit evidence.

Revision ID: 20260914_16
Revises: 20260914_15
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_16"
down_revision = "20260914_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("books", sa.Column("publication_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "publication_year")
