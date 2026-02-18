"""
BOT-01..04: Авторизация запросов от бот-контейнера к Backend.
Shared secret X-Bot-Token (не Telegram-токен).
"""
import hmac

from fastapi import Header, HTTPException

from app.config import BOT_API_TOKEN


def require_bot_token(x_bot_token: str = Header(..., alias="X-Bot-Token")) -> None:
    if not BOT_API_TOKEN:
        raise HTTPException(status_code=503, detail="BOT_API_TOKEN not configured")
    if not hmac.compare_digest(x_bot_token, BOT_API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid bot token")
