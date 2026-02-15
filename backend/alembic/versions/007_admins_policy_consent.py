"""Добавление согласия с Политикой конфиденциальности (ADM-09).

Revision ID: 007
Revises: 006
Create Date: 2026-02-15

Колонки policy_consent_at и policy_consent_version в admins.
До принятия согласия (NULL) доступ к админ-эндпоинтам возвращает 403.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("policy_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admins", sa.Column("policy_consent_version", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("admins", "policy_consent_version")
    op.drop_column("admins", "policy_consent_at")
