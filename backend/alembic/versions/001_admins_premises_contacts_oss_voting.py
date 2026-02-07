"""LOST-01: admins, premises, contacts, oss_voting (SR-LOST01-002..005)

Revision ID: 001
Revises:
Create Date: Initial schema

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SR-LOST01-002: таблица admins (белый список)
    op.create_table(
        "admins",
        sa.Column("telegram_id", sa.String(32), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_check_constraint(
        "admins_role_check",
        "admins",
        '"role" IN (\'administrator\', \'super_administrator\')',
    )

    # SR-LOST01-003: таблица помещений
    op.create_table(
        "premises",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cadastral_number", sa.String(64), nullable=True),
        sa.Column("area", sa.Numeric(12, 2), nullable=True),
        sa.Column("entrance", sa.String(16), nullable=True),
        sa.Column("floor", sa.String(16), nullable=True),
        sa.Column("premises_type", sa.String(64), nullable=True),
        sa.Column("premises_number", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_premises_entrance_floor", "premises", ["entrance", "floor", "premises_type", "premises_number"], unique=False)

    # SR-LOST01-004, BE-02: таблица контактов (ПДн в зашифрованном виде + Blind Index)
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("premise_id", sa.Integer(), sa.ForeignKey("premises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("telegram_id", sa.Text(), nullable=True),
        sa.Column("how_to_address", sa.Text(), nullable=True),
        sa.Column("phone_idx", sa.String(64), nullable=True),
        sa.Column("email_idx", sa.String(64), nullable=True),
        sa.Column("telegram_id_idx", sa.String(64), nullable=True),
        sa.Column("registered_in_ed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_version", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_premise_id", "contacts", ["premise_id"], unique=False)
    op.create_index("ix_contacts_phone_idx", "contacts", ["phone_idx"], unique=False)
    op.create_index("ix_contacts_email_idx", "contacts", ["email_idx"], unique=False)
    op.create_index("ix_contacts_telegram_id_idx", "contacts", ["telegram_id_idx"], unique=False)
    op.create_check_constraint(
        "contacts_status_check",
        "contacts",
        "status IN ('pending', 'validated', 'inactive')",
    )

    # SR-LOST01-005: голосование_в_ОСС
    op.create_table(
        "oss_voting",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position_for", sa.String(256), nullable=True),
        sa.Column("vote_format", sa.String(64), nullable=True),
        sa.Column("voted_in_ed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("voted", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oss_voting_contact_id", "oss_voting", ["contact_id"], unique=False)


def downgrade() -> None:
    op.drop_table("oss_voting")
    op.drop_table("contacts")
    op.drop_table("premises")
    op.drop_table("admins")
