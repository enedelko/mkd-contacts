"""Expand registered_in_ed values to none/account/owner and migrate existing data.

Revision ID: 010
Revises: 009
Create Date: 2026-03-04

Изменение семантики registered_in_ed: вместо yes/no теперь none/account/owner.
Миграция переводит существующие значения yes/no/true/false/1/0 в owner/none.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  conn = op.get_bind()

  # Нормализуем существующие строковые значения registered_in_ed
  conn.execute(
    sa.text(
      """
      UPDATE contacts
      SET registered_in_ed = 'owner'
      WHERE registered_in_ed IN ('yes', 'true', 'True', '1')
      """
    )
  )
  conn.execute(
    sa.text(
      """
      UPDATE contacts
      SET registered_in_ed = 'none'
      WHERE registered_in_ed IN ('no', 'false', 'False', '0')
      """
    )
  )


def downgrade() -> None:
  conn = op.get_bind()

  # Возврат к yes/no для обратной совместимости: owner->yes, остальное->no
  conn.execute(
    sa.text(
      """
      UPDATE contacts
      SET registered_in_ed = 'yes'
      WHERE registered_in_ed = 'owner'
      """
    )
  )
  conn.execute(
    sa.text(
      """
      UPDATE contacts
      SET registered_in_ed = 'no'
      WHERE registered_in_ed IS NULL OR registered_in_ed IN ('none', 'account')
      """
    )
  )

