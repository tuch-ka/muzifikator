"""generation files

Revision ID: d1b86ca252bb
Revises: 97dccce59c0f
Create Date: 2026-11-26 12:48:27.374791

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1b86ca252bb"
down_revision: str | Sequence[str] | None = "97dccce59c0f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_files",
        sa.Column("generation_id", sa.String(length=32), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["generation_id"], ["generations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("generation_id", "format"),
    )


def downgrade() -> None:
    op.drop_table("generation_files")
