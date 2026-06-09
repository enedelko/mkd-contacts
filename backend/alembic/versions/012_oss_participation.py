"""CORE-05: таблица oss_participation (участие в голосовании ОСС).

Revision ID: 012
Revises: 011
Create Date: 2026-06-09

SR-CORE05-001: premise_id, ownership_share, participated, imported_at, import_batch_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oss_participation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "premise_id",
            sa.String(64),
            sa.ForeignKey("premises.cadastral_number", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("share_nominal", sa.Numeric(10, 6), nullable=False),
        sa.Column("ownership_share", sa.Numeric(10, 6), nullable=False),
        sa.Column("participated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("premise_id", "share_nominal", name="uq_oss_participation_premise_nominal"),
    )
    op.create_index("ix_oss_participation_premise_id", "oss_participation", ["premise_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_oss_participation_premise_id", table_name="oss_participation")
    op.drop_table("oss_participation")
