"""
BE-03: GET /api/admin/audit — просмотр аудит-лога.
Доступ только для администратора (SR-BE03-005, SR-BE03-006).
SR-BE03-008..014: фильтры по дате, entity_id; подписи; ссылки.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.crypto import decrypt
from app.db import get_db
from app.jwt_utils import require_admin_with_consent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _build_entity_label(premises_type: str | None, premises_number: str | None, entrance: str | None) -> str | None:
    """SR-BE03-010: человекочитаемая подпись контакта по его помещению."""
    if not premises_type and not premises_number:
        return None
    parts = []
    if premises_type and premises_number:
        parts.append(f"{premises_type} {premises_number}")
    elif premises_number:
        parts.append(premises_number)
    elif premises_type:
        parts.append(premises_type)
    if entrance:
        parts.append(f"подъезд {entrance}")
    return ", ".join(parts)


@router.get("/audit")
def list_audit(
    entity_type: str | None = Query(None, description="Фильтр по типу сущности: contact, admin, bot_alias, contacts_template"),
    action: str | None = Query(None, description="Фильтр по действию"),
    user_id: str | None = Query(None, description="Фильтр по ID пользователя"),
    entity_id: str | None = Query(None, description="Фильтр по ID записи (SR-BE03-009)"),
    from_date: str | None = Query(None, description="Начало диапазона дат, ISO (SR-BE03-008)"),
    to_date: str | None = Query(None, description="Конец диапазона дат, ISO (SR-BE03-008)"),
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
        clauses.append("a.entity_type != 'admin'")
    if entity_type:
        clauses.append("a.entity_type = :et")
        params["et"] = entity_type
    if action:
        clauses.append("a.action = :act")
        params["act"] = action
    if user_id:
        clauses.append("a.user_id = :uid")
        params["uid"] = user_id
    if entity_id:
        clauses.append("a.entity_id = :eid")
        params["eid"] = entity_id
    if from_date:
        clauses.append("a.created_at >= :from_date::date")
        params["from_date"] = from_date
    if to_date:
        clauses.append("a.created_at < :to_date::date + interval '1 day'")
        params["to_date"] = to_date

    where = (" AND ".join(clauses)) if clauses else "1=1"

    select_sql = (
        "SELECT a.id, a.entity_type, a.entity_id, a.action, "
        "a.old_value, a.new_value, a.user_id, a.ip, a.created_at, "
        "p.premises_type, p.premises_number, p.entrance, "
        "adm.full_name, "
        "c.telegram_id AS contact_tg_enc "
        "FROM audit_log a "
        "LEFT JOIN contacts c ON a.entity_type = 'contact' "
        "AND a.entity_id ~ '^\\d+$' "
        "AND c.id = CAST(CASE WHEN a.entity_id ~ '^\\d+$' THEN a.entity_id END AS INTEGER) "
        "LEFT JOIN premises p ON p.cadastral_number = c.premise_id "
        "LEFT JOIN admins adm ON adm.telegram_id = a.user_id "
        f"WHERE {where} ORDER BY a.id DESC LIMIT :lim OFFSET :off"
    )

    count_sql = (
        "SELECT COUNT(*) FROM audit_log a "
        f"WHERE {where}"
    )

    with get_db() as db:
        rows = db.execute(text(select_sql), params).fetchall()
        count_row = db.execute(
            text(count_sql),
            {k: v for k, v in params.items() if k not in ("lim", "off")},
        ).fetchone()

    items = []
    for r in rows:
        uid = r[6]
        user_label = r[12] or None
        user_id_resolved = None

        if not uid and r[13]:
            try:
                user_id_resolved = decrypt(r[13])
            except Exception:
                logger.debug("decrypt contact telegram_id failed for audit row %s", r[0])

        entity_label = _build_entity_label(r[9], r[10], r[11]) if r[1] == "contact" else None

        items.append({
            "id": r[0],
            "entity_type": r[1],
            "entity_id": r[2],
            "action": r[3],
            "old_value": r[4],
            "new_value": r[5],
            "user_id": uid,
            "ip": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
            "entity_label": entity_label,
            "user_label": user_label,
            "user_id_resolved": user_id_resolved,
        })

    return {"items": items, "total": count_row[0] if count_row else 0}
