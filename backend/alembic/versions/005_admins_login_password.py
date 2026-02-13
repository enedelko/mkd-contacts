"""Добавление входа по логину/паролю: login, password_hash в admins.

Revision ID: 005
Revises: 004
Create Date: 2026-02-13

Администратор может входить по Telegram или по логину/паролю.
password_hash — bcrypt (passlib).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("login", sa.String(64), nullable=True))
    op.add_column("admins", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_index("ix_admins_login", "admins", ["login"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_admins_login", table_name="admins")
    op.drop_column("admins", "password_hash")
    op.drop_column("admins", "login")
