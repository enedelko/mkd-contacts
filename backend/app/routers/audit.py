"""
BE-03: GET /api/admin/audit — просмотр аудит-лога.
Доступ только для администратора (SR-BE03-005, SR-BE03-006).
SR-BE03-008..015: фильтры по дате, entity_id; подписи; ссылки; экспорт XLSX.
"""
import io
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import text

from app.crypto import decrypt
from app.db import get_db
from app.jwt_utils import require_admin_with_consent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

EXPORT_MAX_ROWS = 10000

_SELECT_COLUMNS = (
    "SELECT a.id, a.entity_type, a.entity_id, a.action, "
    "a.old_value, a.new_value, a.user_id, a.ip, a.created_at, "
    "p.premises_type, p.premises_number, p.entrance, "
    "adm.full_name, "
    "c.telegram_id AS contact_tg_enc "
)

_FROM_JOINS = (
    "FROM audit_log a "
    "LEFT JOIN contacts c ON a.entity_type = 'contact' "
    "AND a.entity_id ~ '^\\d+$' "
    "AND c.id = CAST(CASE WHEN a.entity_id ~ '^\\d+$' THEN a.entity_id END AS INTEGER) "
    "LEFT JOIN premises p ON p.cadastral_number = c.premise_id "
    "LEFT JOIN admins adm ON adm.telegram_id = a.user_id "
)


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


def _build_where(
    payload: dict[str, Any],
    entity_type: str | None,
    action: str | None,
    user_id: str | None,
    entity_id: str | None,
    from_date: str | None,
    to_date: str | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

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
        clauses.append("a.created_at >= CAST(:from_date AS date)")
        params["from_date"] = from_date
    if to_date:
        clauses.append("a.created_at < CAST(:to_date AS date) + interval '1 day'")
        params["to_date"] = to_date

    where = " AND ".join(clauses) if clauses else "1=1"
    return where, params


def _row_to_item(r: Any) -> dict[str, Any]:
    uid = r[6]
    user_label = r[12] or None
    user_id_resolved = None

    if not uid and r[13]:
        try:
            user_id_resolved = decrypt(r[13])
        except Exception:
            logger.debug("decrypt contact telegram_id failed for audit row %s", r[0])

    entity_label = _build_entity_label(r[9], r[10], r[11]) if r[1] == "contact" else None

    return {
        "id": r[0],
        "entity_type": r[1],
        "entity_id": r[2],
        "action": r[3],
        "old_value": r[4],
        "new_value": r[5],
        "user_id": uid,
        "ip": r[7],
        "created_at": r[8],
        "entity_label": entity_label,
        "user_label": user_label,
        "user_id_resolved": user_id_resolved,
    }


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
    where, params = _build_where(payload, entity_type, action, user_id, entity_id, from_date, to_date)
    params["lim"] = limit
    params["off"] = offset

    select_sql = f"{_SELECT_COLUMNS}{_FROM_JOINS}WHERE {where} ORDER BY a.id DESC LIMIT :lim OFFSET :off"
    count_sql = f"SELECT COUNT(*) FROM audit_log a WHERE {where}"

    with get_db() as db:
        rows = db.execute(text(select_sql), params).fetchall()
        count_row = db.execute(
            text(count_sql),
            {k: v for k, v in params.items() if k not in ("lim", "off")},
        ).fetchone()

    items = []
    for r in rows:
        item = _row_to_item(r)
        item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
        items.append(item)

    return {"items": items, "total": count_row[0] if count_row else 0}


_ACTION_LABELS = {
    "insert": "Создание",
    "update": "Обновление",
    "delete": "Удаление",
    "select": "Просмотр",
    "status_change": "Смена статуса",
    "premise_removed": "Отвязка помещения",
    "bot_answers_update": "Обновление (бот)",
    "forget": "Удаление данных",
    "password_change": "Смена пароля",
    "policy_consent": "Согласие с политикой",
    "export": "Экспорт",
}

_ENTITY_TYPE_LABELS = {
    "contact": "Контакт",
    "admin": "Админ",
    "bot_alias": "Бот-алиас",
    "contacts_template": "Шаблон контактов",
}

_XLSX_HEADERS = ["ID", "Время", "Сущность", "Запись", "Действие", "Старое", "Новое", "Пользователь", "IP"]


@router.get("/audit/export")
def export_audit(
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    user_id: str | None = Query(None),
    entity_id: str | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    payload: dict = Depends(require_admin_with_consent),
) -> Response:
    """SR-BE03-015: экспорт отфильтрованного аудит-лога в XLSX без пагинации."""
    import openpyxl

    where, params = _build_where(payload, entity_type, action, user_id, entity_id, from_date, to_date)
    params["lim"] = EXPORT_MAX_ROWS

    select_sql = f"{_SELECT_COLUMNS}{_FROM_JOINS}WHERE {where} ORDER BY a.id DESC LIMIT :lim"

    with get_db() as db:
        rows = db.execute(text(select_sql), params).fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Аудит-лог"
    ws.append(_XLSX_HEADERS)

    for r in rows:
        item = _row_to_item(r)
        created = item["created_at"]
        time_str = created.strftime("%d.%m.%Y %H:%M:%S") if isinstance(created, datetime) else str(created or "")
        entity_type_label = _ENTITY_TYPE_LABELS.get(item["entity_type"], item["entity_type"])
        record_label = item["entity_label"] or item["entity_id"] or ""
        action_label = _ACTION_LABELS.get(item["action"], item["action"])
        user_display = item["user_label"] or item["user_id"] or item["user_id_resolved"] or "аноним"

        ws.append([
            item["id"],
            time_str,
            entity_type_label,
            record_label,
            action_label,
            item["old_value"] or "",
            item["new_value"] or "",
            user_display,
            item["ip"] or "",
        ])

    buf = io.BytesIO()
    wb.save(buf)

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="audit_log.xlsx"'},
    )
