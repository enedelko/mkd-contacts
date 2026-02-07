"""
BE-02: Шифрование ПДн (phone, email, telegram_id, как обращаться).
Ключ только из файла (SR-BE02-005, SR-BE02-006). Blind Index для поиска (SR-BE02-008).
"""
import hashlib
import hmac
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import BLIND_INDEX_PEPPER, MASTER_KEY_PATH

# Путь к ключу: Docker Secrets или bind mount (SR-BE02-005)
_KEY_PATH = Path(MASTER_KEY_PATH)
_fernet: Fernet | None = None


def _load_key() -> bytes:
    """Загрузить мастер-ключ из файла. Не стартовать без ключа (AF-1)."""
    import base64
    if not _KEY_PATH.exists():
        raise SystemExit(
            "BE-02 AF-1: Master key file not found at %s. "
            "Mount key via Docker Secrets or bind mount (read-only)." % _KEY_PATH
        )
    raw = _KEY_PATH.read_bytes().strip()
    if len(raw) < 32:
        raise SystemExit("BE-02: Master key file must be at least 32 bytes.")
    # Fernet: 44-char base64 key or derive from raw
    try:
        if len(raw) == 44 and raw.decode("ascii", errors="strict").replace("-", "").replace("_", "").replace("=", "").isalnum():
            Fernet(raw)  # validate
            return raw
    except Exception:
        pass
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"mkd-contacts-fernet", iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(raw))


def get_fernet() -> Fernet:
    """Ленивая инициализация Fernet (AES-256)."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def encrypt(plain: str | None) -> str | None:
    """Шифровать строку (SR-BE02-001..003, SR-BE02-010). Пустые — None."""
    if plain is None or not plain.strip():
        return None
    return get_fernet().encrypt(plain.strip().encode("utf-8")).decode("ascii")


def decrypt(cipher: str | None) -> str | None:
    """Расшифровать. При ошибке — None и логировать (AF-2)."""
    if cipher is None or not cipher.strip():
        return None
    try:
        return get_fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken:
        import logging
        logging.getLogger(__name__).warning("BE-02 AF-2: Decryption failed for field (corrupt or wrong key)")
        return None


# --- Blind Index (SR-BE02-008) ---

def _normalize_phone(value: str | None) -> str:
    """Только цифры, лидирующая 8 -> 7."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("8") and len(digits) >= 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return digits[:11] or ""


def _normalize_email(value: str | None) -> str:
    """Нижний регистр, без пробелов."""
    if not value:
        return ""
    return value.lower().strip().replace(" ", "")


def _normalize_telegram_id(value: str | None) -> str:
    """Строковый формат."""
    if value is None:
        return ""
    return str(value).strip()


def blind_index_phone(value: str | None) -> str | None:
    """HMAC-SHA256(pepper, normalized_phone) -> hex. Без pepper — не создавать индекс."""
    if not BLIND_INDEX_PEPPER:
        return None
    n = _normalize_phone(value)
    if not n:
        return None
    return hmac.new(
        BLIND_INDEX_PEPPER.encode("utf-8"),
        n.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def blind_index_email(value: str | None) -> str | None:
    if not BLIND_INDEX_PEPPER:
        return None
    n = _normalize_email(value)
    if not n:
        return None
    return hmac.new(
        BLIND_INDEX_PEPPER.encode("utf-8"),
        n.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def blind_index_telegram_id(value: str | None) -> str | None:
    if not BLIND_INDEX_PEPPER:
        return None
    n = _normalize_telegram_id(value)
    if not n:
        return None
    return hmac.new(
        BLIND_INDEX_PEPPER.encode("utf-8"),
        n.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
