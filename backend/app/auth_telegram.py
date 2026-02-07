"""
ADM-01: Проверка данных Telegram Login Widget (hash) и выдача JWT.
Белый список — таблица admins в БД (SR-ADM01-003, SR-ADM01-007).
"""
import hashlib
import hmac
import logging
from typing import Any

from app.config import TELEGRAM_BOT_TOKEN
from app.db import get_db

logger = logging.getLogger(__name__)


def verify_telegram_login(params: dict[str, Any]) -> dict[str, Any] | None:
    """
    Проверить hash из Telegram Login Widget.
    Возвращает данные пользователя (id, first_name, username, ...) при успехе, иначе None.
    """
    hash_val = params.get("hash")
    if not hash_val or not TELEGRAM_BOT_TOKEN:
        return None
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items()) if k != "hash" and v is not None
    )
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    expected = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, hash_val):
        return None
    return params


def get_admin_by_telegram_id(telegram_id: str) -> dict | None:
    """Найти админа в белом списке (admins). Возвращает {telegram_id, role} или None."""
    from sqlalchemy import text
    with get_db() as db:
        row = db.execute(
            text("SELECT telegram_id, role FROM admins WHERE telegram_id = :tid"),
            {"tid": str(telegram_id)},
        ).fetchone()
    if not row:
        return None
    return {"telegram_id": row[0], "role": row[1]}
