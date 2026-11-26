"""initial schema

Revision ID: 97dccce59c0f
Revises:
Create Date: 2026-11-26 09:42:59.088606

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from muzifikator.storage.models import UTCDateTime

revision: str = "97dccce59c0f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tts_provider", sa.Text(), nullable=True),
        sa.Column("voice", sa.Text(), nullable=True),
        sa.Column("music_tags", sa.Text(), nullable=True),
        sa.Column("music_seed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=True),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ck_generations_status",
        ),
        sa.CheckConstraint(
            "stage IS NULL OR stage IN ('tts', 'music', 'mix')",
            name="ck_generations_stage",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generations_created_at", "generations", ["created_at"], unique=False)

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_generations_created_at", table_name="generations")
    op.drop_table("generations")
