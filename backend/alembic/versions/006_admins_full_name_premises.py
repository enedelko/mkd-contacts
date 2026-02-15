"""Добавление full_name и premises в admins для раздела 9 Политики конфиденциальности.

Revision ID: 006
Revises: 005
Create Date: 2026-02-15

Колонки ФИО и помещение (например Ап.96). В миграции существующие строки
заполняются прочерками.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column("admins", sa.Column("premises", sa.String(128), nullable=True))
    op.execute("UPDATE admins SET full_name = '—' WHERE full_name IS NULL")
    op.execute("UPDATE admins SET premises = '—' WHERE premises IS NULL")


def downgrade() -> None:
    op.drop_column("admins", "premises")
    op.drop_column("admins", "full_name")
