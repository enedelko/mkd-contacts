"""
Настройки приложения. Секреты не в репозитории (BE-02, ADM-01).
"""
import os
from pathlib import Path


def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# Database (LOST-01)
DATABASE_URL = _env("DATABASE_URL", "postgresql://mkd:mkd_secret@localhost:5432/mkd_contacts")

# BE-02: мастер-ключ только из файла (SR-BE02-005). Путь: Docker Secrets или bind mount.
MASTER_KEY_PATH = _env("MASTER_KEY_PATH", "/run/secrets/master_key")
# Pepper для Blind Index в env (SR-BE02-008)
BLIND_INDEX_PEPPER = _env("BLIND_INDEX_PEPPER", "")

# ADM-01: Telegram Bot Token для проверки Login Widget hash
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "")
# JWT (ADM-01). Рекомендуется 8–12 ч для админки: при потере телефона сессия истечёт сама.
JWT_SECRET = _env("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRE_SECONDS = int(_env("JWT_ACCESS_EXPIRE_SECONDS", "36000") or "36000")  # по умолчанию 10 ч

# BOT-01..04: shared secret for bot→backend HTTP calls (not the Telegram bot token)
BOT_API_TOKEN = _env("BOT_API_TOKEN", "")

# CORS (опционально)
CORS_ORIGINS = _env("CORS_ORIGINS", "*").split(",")

# FE-04: Turnstile (Cloudflare). Если не задан — капча не проверяется (тест/разработка).
TURNSTILE_SECRET_KEY = _env("TURNSTILE_SECRET_KEY", "")
# Лимит отправок с одного IP в час (FE-04 AF-2)
SUBMIT_RATE_LIMIT_PER_HOUR = int(_env("SUBMIT_RATE_LIMIT_PER_HOUR", "10") or "10")
