"""
Вход по логину/паролю для администраторов (альтернатива Telegram).
Хранение bcrypt-хеша в admins.password_hash.
"""
import logging
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import text

from app.db import get_db

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# bcrypt принимает не более 72 байт; длиннее — обрезаем по границе UTF-8
BCRYPT_MAX_BYTES = 72


def _truncate_for_bcrypt(password: str) -> str:
    data = password.encode("utf-8")
    if len(data) <= BCRYPT_MAX_BYTES:
        return password
    return data[:BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(_truncate_for_bcrypt(password))


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return pwd_ctx.verify(_truncate_for_bcrypt(plain), hashed)
    except Exception:
        return False


def get_admin_by_login(login: str) -> dict[str, Any] | None:
    """Найти админа по логину. Возвращает {telegram_id, role, password_hash} или None."""
    if not login or not login.strip():
        return None
    with get_db() as db:
        row = db.execute(
            text(
                "SELECT telegram_id, role, password_hash FROM admins WHERE login = :login"
            ),
            {"login": login.strip().lower()},
        ).fetchone()
    if not row:
        return None
    return {
        "telegram_id": row[0],
        "role": row[1],
        "password_hash": row[2],
    }


def get_admin_by_telegram_id_for_password(telegram_id: str) -> dict[str, Any] | None:
    """Найти админа по telegram_id (для смены пароля). Возвращает {telegram_id, role, password_hash} или None."""
    with get_db() as db:
        row = db.execute(
            text(
                "SELECT telegram_id, role, password_hash FROM admins WHERE telegram_id = :tid"
            ),
            {"tid": str(telegram_id)},
        ).fetchone()
    if not row:
        return None
    return {
        "telegram_id": row[0],
        "role": row[1],
        "password_hash": row[2],
    }


def set_admin_password(telegram_id: str, new_password: str) -> None:
    """Установить новый password_hash для админа по telegram_id."""
    new_hash = hash_password(new_password)
    with get_db() as db:
        db.execute(
            text(
                "UPDATE admins SET password_hash = :h WHERE telegram_id = :tid"
            ),
            {"h": new_hash, "tid": str(telegram_id)},
        )
        db.commit()
    logger.info("Password updated for admin telegram_id=%s", telegram_id)
