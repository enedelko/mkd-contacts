"""Возвращение колонки registered_in_ed в contacts (теперь varchar: yes/no/null).

Revision ID: 004
Revises: 003
Create Date: 2026-02-12

Поле «Зарегистрированы ли вы в Электронном доме» возвращено в анкету.
Тип изменён с boolean на varchar для хранения yes/no/null.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("registered_in_ed", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "registered_in_ed")
