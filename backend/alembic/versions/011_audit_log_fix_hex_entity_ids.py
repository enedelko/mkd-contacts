"""Fix audit_log: replace hex entity_id (blind index) with contact.id, fill user_id.

Revision ID: 011
Revises: 010
Create Date: 2026-03-06

Бот-действия (bot_answers_update, forget) писали в entity_id blind index
(telegram_id_idx) вместо contact.id, а user_id оставляли NULL.
Миграция: для каждой hex-записи находим контакты по telegram_id_idx,
заменяем entity_id на contact.id, заполняем user_id из расшифрованного
telegram_id. Если контактов несколько — создаём по строке на каждый.
Если контакт удалён (forget) — запись остаётся без изменений.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.crypto import decrypt

    conn = op.get_bind()

    hex_rows = conn.execute(text(
        "SELECT id, entity_id, action, user_id, old_value, new_value, ip, created_at "
        "FROM audit_log "
        "WHERE entity_type = 'contact' AND entity_id ~ '^[a-f0-9]{20,}$' "
        "ORDER BY id"
    )).fetchall()

    for row in hex_rows:
        audit_id, tg_idx, action, uid, old_val, new_val, ip, created_at = row

        contacts = conn.execute(text(
            "SELECT id, telegram_id FROM contacts WHERE telegram_id_idx = :idx"
        ), {"idx": tg_idx}).fetchall()

        if not contacts:
            continue

        tg_decrypted = None
        for c in contacts:
            if c[1]:
                tg_decrypted = decrypt(c[1])
                break

        resolved_uid = uid or tg_decrypted

        conn.execute(text(
            "UPDATE audit_log SET entity_id = :eid, user_id = COALESCE(user_id, :uid) WHERE id = :aid"
        ), {"eid": str(contacts[0][0]), "uid": resolved_uid, "aid": audit_id})

        for c in contacts[1:]:
            conn.execute(text(
                "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user_id, ip, created_at) "
                "VALUES ('contact', :eid, :act, :old, :new, :uid, :ip, :cat)"
            ), {
                "eid": str(c[0]), "act": action,
                "old": old_val, "new": new_val,
                "uid": resolved_uid, "ip": ip, "cat": created_at,
            })


def downgrade() -> None:
    pass
