"""
ADM-04: Управление белым списком админов (только super_administrator).
ADM-05: Логирование действий суперадмина в audit_log (SR-ADM05-001, SR-ADM05-002, SR-ADM05-003).
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text

from app.auth_password import hash_password
from app.db import get_db
from app.jwt_utils import require_super_admin

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str | None:
    """IP клиента (за nginx — X-Forwarded-For / X-Real-IP)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.headers.get("x-real-ip"):
        return request.headers.get("x-real-ip").strip() or None
    return request.client.host if request.client else None


def _audit_log(db, entity_type: str, entity_id: str, action: str, old_value: str | None, new_value: str | None, user_id: str | None, ip: str | None) -> None:
    """ADM-05: запись в аудит-лог (BE-03)."""
    try:
        db.execute(
            text(
                "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user_id, ip) "
                "VALUES (:et, :eid, :act, :old, :new, :uid, :ip)"
            ),
            {"et": entity_type, "eid": entity_id, "act": action, "old": old_value, "new": new_value, "uid": user_id, "ip": ip},
        )
    except Exception as e:
        logger.warning("audit_log insert failed: %s", e)

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


class AddAdminBody(BaseModel):
    telegram_id: str
    role: str = "administrator"
    login: str | None = None
    password: str | None = None


class PatchAdminBody(BaseModel):
    """Установка или смена логина/пароля для админа (только суперадмин)."""
    login: str | None = None
    password: str | None = None


@router.get("/admins")
def list_admins(
    payload: dict = Depends(require_super_admin),
) -> list[dict[str, Any]]:
    """ADM-04: Список администраторов (без чувствительных данных)."""
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT telegram_id, role, created_at, login FROM admins ORDER BY created_at"
            )
        ).fetchall()
    return [
        {
            "telegram_id": r[0],
            "role": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "has_login": bool(r[3]),
        }
        for r in rows
    ]


@router.post("/admins")
def add_admin(
    request: Request,
    body: AddAdminBody,
    payload: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """ADM-04: Добавить администратора (только administrator). Опционально login и password. ADM-05: пишем в audit_log."""
    if body.role != "administrator":
        raise HTTPException(status_code=400, detail="Only role 'administrator' can be added via API")
    tid = body.telegram_id.strip()
    login_val = (body.login or "").strip().lower() or None
    password_hash = hash_password(body.password) if body.password else None
    with get_db() as db:
        db.execute(
            text(
                "INSERT INTO admins (telegram_id, role, login, password_hash) "
                "VALUES (:tid, :role, :login, :ph) ON CONFLICT (telegram_id) DO NOTHING"
            ),
            {"tid": tid, "role": body.role, "login": login_val, "ph": password_hash},
        )
        _audit_log(db, "admin", tid, "insert", None, body.role, payload.get("sub"), _client_ip(request))
        db.commit()
    logger.info("ADM-04: Admin added telegram_id=%s by sub=%s", tid, payload.get("sub"))
    return {"ok": True, "telegram_id": tid, "role": body.role}


@router.patch("/admins/{telegram_id}")
def patch_admin(
    request: Request,
    telegram_id: str,
    body: PatchAdminBody,
    payload: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """Установить или изменить логин и/или пароль для администратора. ADM-05: пишем в audit_log."""
    with get_db() as db:
        row = db.execute(
            text("SELECT 1 FROM admins WHERE telegram_id = :tid"),
            {"tid": telegram_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Admin not found")
        updates = []
        params = {"tid": telegram_id}
        if body.login is not None:
            login_val = body.login.strip().lower() if body.login else None
            updates.append("login = :login")
            params["login"] = login_val
        if body.password is not None and (body.password or "").strip():
            if len((body.password or "").strip()) < 8:
                raise HTTPException(
                    status_code=400,
                    detail="Пароль должен быть не короче 8 символов",
                )
            updates.append("password_hash = :ph")
            params["ph"] = hash_password(body.password)
        if updates:
            db.execute(
                text(
                    "UPDATE admins SET " + ", ".join(updates) + " WHERE telegram_id = :tid"
                ),
                params,
            )
            parts = []
            if body.login is not None:
                parts.append("login")
            if body.password is not None and (body.password or "").strip():
                parts.append("password")
            _audit_log(db, "admin", telegram_id, "update", None, ",".join(parts) if parts else "login,password", payload.get("sub"), _client_ip(request))
            db.commit()
    logger.info("ADM-04: Admin patched telegram_id=%s (login/password) by sub=%s", telegram_id, payload.get("sub"))
    return {"ok": True, "telegram_id": telegram_id}


@router.delete("/admins/{telegram_id}")
def delete_admin(
    request: Request,
    telegram_id: str,
    payload: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """ADM-04: Удалить из белого списка. Суперадмин не может удалить себя (SR-ADM04-003). ADM-05: пишем в audit_log."""
    current_sub = payload.get("sub")
    if current_sub == telegram_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    with get_db() as db:
        target = db.execute(
            text("SELECT role FROM admins WHERE telegram_id = :tid"),
            {"tid": telegram_id},
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")
        if target[0] == "super_administrator":
            other_super = db.execute(
                text(
                    "SELECT 1 FROM admins WHERE role = 'super_administrator' AND telegram_id != :tid LIMIT 1"
                ),
                {"tid": telegram_id},
            ).fetchone()
            if not other_super:
                raise HTTPException(status_code=400, detail="Cannot remove the last super_administrator")
        role_before = target[0]
        db.execute(text("DELETE FROM admins WHERE telegram_id = :tid"), {"tid": telegram_id})
        _audit_log(db, "admin", telegram_id, "delete", role_before, None, current_sub, _client_ip(request))
        db.commit()
    logger.info("ADM-04: Admin removed telegram_id=%s by sub=%s", telegram_id, current_sub)
    return {"ok": True, "telegram_id": telegram_id}
