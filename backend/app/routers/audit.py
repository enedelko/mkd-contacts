"""
BE-03: GET /api/admin/audit — просмотр аудит-лога.
Доступ только для администратора (SR-BE03-005, SR-BE03-006).
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.db import get_db
from app.jwt_utils import require_admin_with_consent

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit")
def list_audit(
    entity_type: str | None = Query(None, description="Фильтр по типу сущности: contact, premise, admin (ADM-05)"),
    action: str | None = Query(None, description="Фильтр по действию: insert, update, delete, select, status_change"),
    user_id: str | None = Query(None, description="Фильтр по ID пользователя"),
    limit: int = Query(50, ge=1, le=500, description="Кол-во записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    BE-03 / SR-BE03-005: список записей аудит-лога с фильтрами.
    ПДн не хранятся в логе (SR-BE03-006).
    SR-ADM05-004: записи entity_type=admin видны только суперадмину.
    """
    clauses = []
    params: dict[str, Any] = {"lim": limit, "off": offset}

    if payload.get("role") != "super_administrator":
        clauses.append("entity_type != 'admin'")
    if entity_type:
        clauses.append("entity_type = :et")
        params["et"] = entity_type
    if action:
        clauses.append("action = :act")
        params["act"] = action
    if user_id:
        clauses.append("user_id = :uid")
        params["uid"] = user_id

    where = (" AND ".join(clauses)) if clauses else "1=1"

    with get_db() as db:
        rows = db.execute(
            text(
                f"SELECT id, entity_type, entity_id, action, old_value, new_value, user_id, ip, created_at "
                f"FROM audit_log WHERE {where} ORDER BY id DESC LIMIT :lim OFFSET :off"
            ),
            params,
        ).fetchall()

        count_row = db.execute(
            text(f"SELECT COUNT(*) FROM audit_log WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("lim", "off")},
        ).fetchone()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "entity_type": r[1],
            "entity_id": r[2],
            "action": r[3],
            "old_value": r[4],
            "new_value": r[5],
            "user_id": r[6],
            "ip": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        })

    return {"items": items, "total": count_row[0] if count_row else 0}
