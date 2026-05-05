"""Bot configuration loaded from environment variables."""
import os


def _normalize_telegram_socks_proxy(url: str) -> str:
    """python_socks (aiogram) не знает схему socks5h:// — только socks5://; удалённый DNS через SOCKS задаётся коннектором aiogram (rdns)."""
    u = url.strip()
    if u.casefold().startswith("socks5h://"):
        return "socks5://" + u[10:]  # len("socks5h://")
    return u


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_SOCKS5_PROXY = _normalize_telegram_socks_proxy((os.getenv("TELEGRAM_SOCKS5_PROXY") or "").strip())
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BOT_API_TOKEN = os.environ["BOT_API_TOKEN"]
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PATH = f"/api/tg-wh/{WEBHOOK_SECRET}" if WEBHOOK_SECRET else "/api/tg-wh/hook"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")
LISTEN_PORT = int(os.getenv("BOT_PORT", "8443"))
SESSION_DB_PATH = os.getenv("SESSION_DB_PATH", "/data/sessions.db")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
# Только отладка: логировать curl с реальным TELEGRAM_BOT_TOKEN (и URL прокси). По умолчанию выключено.
TELEGRAM_LOG_CURL_WITH_TOKEN = (os.getenv("TELEGRAM_LOG_CURL_WITH_TOKEN") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
