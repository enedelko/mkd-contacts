"""Переименование position_for → barrier_vote, удаление voted_in_ed и registered_in_ed.

Revision ID: 003
Revises: 002
Create Date: 2026-02-12

Поля vote_for/registered_ed убраны из анкеты (FE-04).
Вместо position_for используется barrier_vote (for/against/undecided).
voted_in_ed и registered_in_ed больше не используются.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # oss_voting: position_for → barrier_vote
    op.alter_column("oss_voting", "position_for", new_column_name="barrier_vote")
    # oss_voting: удалить voted_in_ed
    op.drop_column("oss_voting", "voted_in_ed")
    # contacts: удалить registered_in_ed
    op.drop_column("contacts", "registered_in_ed")


def downgrade() -> None:
    # contacts: восстановить registered_in_ed
    op.add_column("contacts", sa.Column("registered_in_ed", sa.Boolean(), nullable=False, server_default="false"))
    # oss_voting: восстановить voted_in_ed
    op.add_column("oss_voting", sa.Column("voted_in_ed", sa.Boolean(), nullable=False, server_default="false"))
    # oss_voting: barrier_vote → position_for
    op.alter_column("oss_voting", "barrier_vote", new_column_name="position_for")
