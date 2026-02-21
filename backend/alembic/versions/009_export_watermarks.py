"""Export watermarks: canary contact per template download for leak attribution.

Revision ID: 009
Revises: 008
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "export_watermarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_telegram_id", sa.String(32), nullable=False),
        sa.Column("entrance", sa.String(32), nullable=False),
        sa.Column("premise_id", sa.String(64), sa.ForeignKey("premises.cadastral_number", ondelete="RESTRICT"), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("canary_telegram_id", sa.String(32), nullable=False),
        sa.Column("how_to_address", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_export_watermarks_phone_canary_tg",
        "export_watermarks",
        ["phone", "canary_telegram_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_export_watermarks_phone_canary_tg", table_name="export_watermarks")
    op.drop_table("export_watermarks")
