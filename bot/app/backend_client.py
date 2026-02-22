"""
Async HTTP client for bot → backend communication.
All calls use X-Bot-Token header.
"""
import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from app.config import BACKEND_URL, BOT_API_TOKEN

logger = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None


def _headers() -> dict[str, str]:
    return {"X-Bot-Token": BOT_API_TOKEN, "Content-Type": "application/json"}


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(base_url=BACKEND_URL, headers=_headers())
    return _session


async def close() -> None:
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def resolve_premise(text: str, telegram_user_id: str | None = None) -> list[dict[str, Any]]:
    s = await _get_session()
    body: dict[str, Any] = {"text": text}
    if telegram_user_id:
        body["telegram_user_id"] = str(telegram_user_id)
    async with s.post("/api/bot/resolve-premise", json=body) as resp:
        if resp.status != 200:
            logger.warning("resolve_premise %s → %s", resp.status, await resp.text())
            return []
        data = await resp.json()
        return data.get("matches", [])


async def add_premise(telegram_user_id: int, premise_id: str) -> dict[str, Any]:
    s = await _get_session()
    async with s.post("/api/bot/premises", json={
        "telegram_user_id": str(telegram_user_id),
        "premise_id": premise_id,
    }) as resp:
        try:
            data = await resp.json()
        except Exception:
            data = {}
        data["_status"] = resp.status
        return data


async def remove_premise(telegram_user_id: int, premise_id: str) -> dict[str, Any]:
    s = await _get_session()
    # Кадастровый номер содержит ':', в URL путь нужно кодировать
    path = f"/api/bot/me/premises/{quote(premise_id, safe='')}"
    async with s.delete(path, json={
        "telegram_user_id": str(telegram_user_id),
        "premise_id": premise_id,
    }) as resp:
        try:
            data = await resp.json()
        except Exception:
            data = {}
        data["_status"] = resp.status
        return data


async def update_answers(telegram_user_id: int, **kwargs: Any) -> dict[str, Any]:
    s = await _get_session()
    body: dict[str, Any] = {"telegram_user_id": str(telegram_user_id)}
    body.update(kwargs)
    async with s.patch("/api/bot/me/answers", json=body) as resp:
        try:
            data = await resp.json()
        except Exception:
            data = {}
        data["_status"] = resp.status
        return data


async def get_my_data(telegram_user_id: int) -> dict[str, Any]:
    s = await _get_session()
    async with s.get("/api/bot/me/data", params={"telegram_user_id": str(telegram_user_id)}) as resp:
        if resp.status != 200:
            return {"premises": []}
        return await resp.json()


async def forget(telegram_user_id: int) -> dict[str, Any]:
    s = await _get_session()
    async with s.delete("/api/bot/me/forget", json={
        "telegram_user_id": str(telegram_user_id),
    }) as resp:
        try:
            data = await resp.json()
        except Exception:
            data = {}
        data["_status"] = resp.status
        return data


async def get_my_role(telegram_user_id: int) -> dict[str, Any]:
    """GET /api/bot/me/role. Returns { role: 'super_administrator'|'administrator'|None }."""
    try:
        s = await _get_session()
        async with s.get("/api/bot/me/role", params={"telegram_user_id": str(telegram_user_id)}) as resp:
            if resp.status != 200:
                logger.warning("get_my_role status=%s body=%s", resp.status, await resp.text())
                return {"role": None}
            data = await resp.json()
            logger.info("get_my_role user_id=%s role=%s", telegram_user_id, data.get("role"))
            return data
    except Exception as e:
        logger.warning("get_my_role failed: %s", e)
        return {"role": None}


async def get_admins_telegram_ids() -> list[str]:
    """GET /api/bot/admins-telegram-ids. Returns list of admin telegram_ids for messaging."""
    try:
        s = await _get_session()
        async with s.get("/api/bot/admins-telegram-ids") as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get("telegram_ids") or []
    except Exception as e:
        logger.warning("get_admins_telegram_ids failed: %s", e)
        return []


async def get_quorum() -> dict[str, Any] | None:
    """GET /api/buildings/default/quorum. Returns None on error or non-200."""
    try:
        s = await _get_session()
        timeout = aiohttp.ClientTimeout(total=5)
        async with s.get("/api/buildings/default/quorum", timeout=timeout) as resp:
            if resp.status != 200:
                logger.warning("get_quorum %s", resp.status)
                return None
            return await resp.json()
    except Exception as e:
        logger.warning("get_quorum failed: %s", e)
        return None
