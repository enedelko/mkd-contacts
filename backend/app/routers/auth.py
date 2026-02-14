"""
ADM-01: Telegram OAuth callback и вход по логину/паролю, выдача JWT (white-list из admins).
Эндпоинт bot-id для построения URL входа в новом окне (popup) вместо iframe.
Поддержка tg_auth_result: oauth.telegram.org в popup возвращает только id в base64 (без hash).
"""
import base64
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.auth_password import (
    get_admin_by_login,
    get_admin_by_telegram_id_for_password,
    set_admin_password,
    verify_password,
)
from app.auth_telegram import get_admin_by_telegram_id, verify_telegram_login
from app.config import TELEGRAM_BOT_TOKEN
from app.jwt_utils import create_access_token, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    login: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login_password(body: LoginBody) -> JSONResponse:
    """Вход по логину и паролю. JWT в том же формате, что и при входе через Telegram."""
    login = (body.login or "").strip()
    if not login:
        return JSONResponse(status_code=400, content={"detail": "Укажите логин"})
    admin = get_admin_by_login(login)
    if not admin:
        logger.info("ADM-01: Login denied for unknown login=%s", login)
        return JSONResponse(status_code=401, content={"detail": "Неверный логин или пароль"})
    if not verify_password(body.password, admin.get("password_hash") or ""):
        logger.info("ADM-01: Login denied for login=%s (bad password)", login)
        return JSONResponse(status_code=401, content={"detail": "Неверный логин или пароль"})
    token = create_access_token(telegram_id=admin["telegram_id"], role=admin["role"])
    logger.info("ADM-01: Login by password login=%s telegram_id=%s role=%s", login, admin["telegram_id"], admin["role"])
    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "bearer",
            "role": admin["role"],
        },
    )


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    payload: dict = Depends(require_admin),
) -> Response:
    """Смена пароля для текущего администратора (по текущему паролю)."""
    sub = payload.get("sub")
    if not sub:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    admin = get_admin_by_telegram_id_for_password(sub)
    if not admin:
        return JSONResponse(status_code=403, content={"detail": "Admin not found"})
    if not admin.get("password_hash"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Пароль не задан. Обратитесь к суперадмину для установки пароля."},
        )
    if not verify_password(body.current_password, admin["password_hash"]):
        return JSONResponse(status_code=400, content={"detail": "Неверный текущий пароль"})
    new = (body.new_password or "").strip()
    if len(new) < 8:
        return JSONResponse(
            status_code=400,
            content={"detail": "Новый пароль должен быть не короче 8 символов"},
        )
    set_admin_password(sub, new)
    return Response(status_code=204)


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
        result = data["result"]
        return JSONResponse(content={
            "bot_id": result["id"],
            "bot_username": result.get("username"),
        })
    except Exception as e:
        logger.warning("getMe failed: %s", e)
        return JSONResponse(status_code=503, content={"detail": "Telegram API unavailable"})


def _decode_tg_auth_result(raw: str) -> dict[str, Any] | None:
    """Декодирует tgAuthResult (base64 JSON). Возвращает dict с id и опционально hash и др."""
    try:
        padded = raw + "=" * (4 - len(raw) % 4) if len(raw) % 4 else raw
        try:
            decoded = base64.b64decode(padded)
        except ValueError:
            decoded = base64.urlsafe_b64decode(padded.replace("-", "+").replace("_", "/"))
        obj = json.loads(decoded)
        if isinstance(obj, dict) and "id" in obj:
            return {k: str(v) if v is not None else None for k, v in obj.items()}
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return None


@router.get("/telegram/callback")
def telegram_callback(
    hash: str | None = Query(None, alias="hash"),
    id: str | None = Query(None),
    first_name: str | None = Query(None),
    username: str | None = Query(None),
    auth_date: str | None = Query(None),
    last_name: str | None = Query(None),
    photo_url: str | None = Query(None),
    tg_auth_result: str | None = Query(None),
) -> JSONResponse:
    """
    ADM-01: Проверка данных от Telegram. Либо hash+id (виджет), либо tg_auth_result (popup oauth.telegram.org).
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

    if tg_auth_result:
        decoded = _decode_tg_auth_result(tg_auth_result)
        if decoded:
            params.update({k: v for k, v in decoded.items() if v is not None})

    if not params.get("id"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing id from Telegram"},
        )

    telegram_id = str(params["id"])

    if params.get("hash"):
        user = verify_telegram_login(params)
        if not user:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Telegram signature"},
            )
        telegram_id = str(user["id"])
    else:
        logger.warning(
            "ADM-01: Login without hash (oauth.telegram.org popup); telegram_id=%s",
            telegram_id,
        )

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
