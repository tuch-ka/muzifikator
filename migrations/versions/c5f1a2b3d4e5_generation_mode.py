"""generation mode

Revision ID: c5f1a2b3d4e5
Revises: d1b86ca252bb
Create Date: 2026-11-26 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5f1a2b3d4e5"
down_revision: str | Sequence[str] | None = "d1b86ca252bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generations",
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="song"),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE generations DROP COLUMN mode")
