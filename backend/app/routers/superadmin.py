"""
ADM-04: Управление белым списком админов (только super_administrator).
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db import get_db
from app.jwt_utils import require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])


class AddAdminBody(BaseModel):
    telegram_id: str
    role: str = "administrator"


@router.get("/admins")
def list_admins(
    payload: dict = Depends(require_super_admin),
) -> list[dict[str, Any]]:
    """ADM-04: Список администраторов (без чувствительных данных)."""
    with get_db() as db:
        rows = db.execute(
            text("SELECT telegram_id, role, created_at FROM admins ORDER BY created_at")
        ).fetchall()
    return [
        {"telegram_id": r[0], "role": r[1], "created_at": r[2].isoformat() if r[2] else None}
        for r in rows
    ]


@router.post("/admins")
def add_admin(
    body: AddAdminBody,
    payload: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """ADM-04: Добавить администратора (только administrator). SR-ADM04-001, SR-ADM04-006."""
    if body.role != "administrator":
        raise HTTPException(status_code=400, detail="Only role 'administrator' can be added via API")
    with get_db() as db:
        db.execute(
            text(
                "INSERT INTO admins (telegram_id, role) VALUES (:tid, :role) ON CONFLICT (telegram_id) DO NOTHING"
            ),
            {"tid": body.telegram_id.strip(), "role": body.role},
        )
        db.commit()
    logger.info("ADM-04: Admin added telegram_id=%s by sub=%s", body.telegram_id, payload.get("sub"))
    return {"ok": True, "telegram_id": body.telegram_id, "role": body.role}


@router.delete("/admins/{telegram_id}")
def delete_admin(
    telegram_id: str,
    payload: dict = Depends(require_super_admin),
) -> dict[str, Any]:
    """ADM-04: Удалить из белого списка. Суперадмин не может удалить себя (SR-ADM04-003)."""
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
        db.execute(text("DELETE FROM admins WHERE telegram_id = :tid"), {"tid": telegram_id})
        db.commit()
    logger.info("ADM-04: Admin removed telegram_id=%s by sub=%s", telegram_id, current_sub)
    return {"ok": True, "telegram_id": telegram_id}
