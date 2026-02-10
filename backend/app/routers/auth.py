"""
ADM-01: Telegram OAuth callback, выдача JWT (white-list из admins).
Эндпоинт bot-id для построения URL входа в новом окне (popup) вместо iframe.
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.auth_telegram import get_admin_by_telegram_id, verify_telegram_login
from app.config import TELEGRAM_BOT_TOKEN
from app.jwt_utils import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/telegram/bot-id")
def telegram_bot_id() -> JSONResponse:
    """
    Возвращает числовой id бота для построения URL oauth.telegram.org (вход в popup, без iframe).
    Вызов getMe через Telegram Bot API.
    """
    if not TELEGRAM_BOT_TOKEN:
        return JSONResponse(status_code=503, content={"detail": "Telegram bot not configured"})
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
            data = r.json()
        if not data.get("ok") or not data.get("result"):
            return JSONResponse(status_code=503, content={"detail": "Telegram API error"})
        return JSONResponse(content={"bot_id": data["result"]["id"]})
    except Exception as e:
        logger.warning("getMe failed: %s", e)
        return JSONResponse(status_code=503, content={"detail": "Telegram API unavailable"})


@router.get("/telegram/callback")
def telegram_callback(
    hash: str | None = Query(None, alias="hash"),
    id: str | None = Query(None),
    first_name: str | None = Query(None),
    username: str | None = Query(None),
    auth_date: str | None = Query(None),
    last_name: str | None = Query(None),
    photo_url: str | None = Query(None),
) -> JSONResponse:
    """
    ADM-01: Проверка данных от Telegram Login Widget и выдача JWT при наличии в white-list.
    Параметры: hash, id, first_name, username, auth_date, ... (как отдаёт Telegram).
    """
    params: dict[str, Any] = {
        "hash": hash,
        "id": id,
        "first_name": first_name,
        "username": username,
        "auth_date": auth_date,
        "last_name": last_name,
        "photo_url": photo_url,
    }
    params = {k: v for k, v in params.items() if v is not None}
    if not params.get("hash") or not params.get("id"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing hash or id from Telegram"},
        )
    user = verify_telegram_login(params)
    if not user:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid Telegram signature"},
        )
    telegram_id = str(user["id"])
    admin = get_admin_by_telegram_id(telegram_id)
    if not admin:
        logger.info("ADM-01: Access denied for telegram_id=%s (not in white-list)", telegram_id)
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied: not in white-list"},
        )
    token = create_access_token(telegram_id=telegram_id, role=admin["role"])
    logger.info("ADM-01: Login telegram_id=%s role=%s", telegram_id, admin["role"])
    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "bearer",
            "role": admin["role"],
        },
    )
