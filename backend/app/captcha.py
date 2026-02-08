"""FE-04: проверка Turnstile (Cloudflare)."""
import logging
from typing import Optional

from app.config import TURNSTILE_SECRET_KEY

logger = logging.getLogger(__name__)


def verify_turnstile(token: Optional[str], remote_ip: Optional[str] = None) -> bool:
    """Проверить токен капчи через Cloudflare siteverify. Если TURNSTILE_SECRET_KEY не задан — возвращает True."""
    if not TURNSTILE_SECRET_KEY:
        return True
    if not token or not token.strip():
        return False
    try:
        import httpx
        r = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET_KEY, "response": token.strip(), "remoteip": remote_ip or ""},
            timeout=10.0,
        )
        data = r.json()
        return data.get("success") is True
    except Exception as e:
        logger.warning("Turnstile verify failed: %s", e)
        return False
