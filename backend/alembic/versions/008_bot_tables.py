"""BOT-01..04: source field, premise_type_aliases, bot_unrecognized.

Revision ID: 008
Revises: 007
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALIASES_SEED = [
    ("Квартира", "Кв.", "кв"),
    ("Квартира", "Кв.", "кварт"),
    ("Квартира", "Кв.", "квартира"),
    ("Квартира", "Кв.", "квартиру"),
    ("Квартира", "Кв.", "квартиры"),
    ("Машино-место", "ММ", "мм"),
    ("Машино-место", "ММ", "мместо"),
    ("Машино-место", "ММ", "м/м"),
    ("Машино-место", "ММ", "машиноместо"),
    ("Машино-место", "ММ", "машино-место"),
    ("Машино-место", "ММ", "парковка"),
    ("Машино-место", "ММ", "парковочное"),
    ("Офис (апартаменты)", "Ап.", "ап"),
    ("Офис (апартаменты)", "Ап.", "апарт"),
    ("Офис (апартаменты)", "Ап.", "апартамент"),
    ("Офис (апартаменты)", "Ап.", "апартаменты"),
    ("Офис (апартаменты)", "Ап.", "оф"),
    ("Офис (апартаменты)", "Ап.", "офис"),
    ("Вспомогательное помещение офисов (кладовка)", "Клад.", "клад"),
    ("Вспомогательное помещение офисов (кладовка)", "Клад.", "кладовка"),
    ("Вспомогательное помещение офисов (кладовка)", "Клад.", "кладовку"),
    ("Вспомогательное помещение офисов (кладовка)", "Клад.", "кладовая"),
    ("Вспомогательное помещение офисов (кладовка)", "Клад.", "хоз"),
    ("БКТ", "БКТ", "бкт"),
]


def upgrade() -> None:
    op.add_column("contacts", sa.Column("source", sa.String(16), server_default="web", nullable=False))

    op.create_table(
        "premise_type_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("premises_type", sa.String(64), nullable=False),
        sa.Column("short_name", sa.String(32), nullable=False),
        sa.Column("alias", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pta_alias", "premise_type_aliases", ["alias"], unique=True)

    op.create_table(
        "bot_unrecognized",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("input_text", sa.String(200), nullable=False),
        sa.Column("telegram_id_idx", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    t = sa.table(
        "premise_type_aliases",
        sa.column("premises_type", sa.String),
        sa.column("short_name", sa.String),
        sa.column("alias", sa.String),
    )
    op.bulk_insert(t, [
        {"premises_type": pt, "short_name": sn, "alias": a}
        for pt, sn, a in ALIASES_SEED
    ])


def downgrade() -> None:
    op.drop_table("bot_unrecognized")
    op.drop_table("premise_type_aliases")
    op.drop_column("contacts", "source")
