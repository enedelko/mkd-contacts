"""
ADM-03: POST /api/admin/contacts — добавление контакта админом.
VAL-01: GET /api/admin/contacts — список контактов; PATCH …/status — смена статуса.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from sqlalchemy import text

from app.client_ip import get_client_ip
from app.db import get_db
from app.import_register import create_watermark
from app.jwt_utils import require_admin_with_consent
from app.crypto import decrypt, encrypt, blind_index_phone, blind_index_email, blind_index_telegram_id
from app.validators import validate_phone, validate_email, validate_telegram_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_STATUSES = ("pending", "validated", "inactive")


@router.get("/contacts")
def list_contacts(
    request: Request,
    entrance: str | None = Query(None, description="Фильтр по подъезду (CORE-03)"),
    premise_id: str | None = Query(None, description="Фильтр по кадастровому номеру помещения"),
    premises_number: str | None = Query(None, description="Поиск по номеру квартиры/помещения"),
    status: str | None = Query(None, description="Фильтр по статусу: pending | validated | inactive"),
    ip: str | None = Query(None, description="Фильтр по IP (ADM-02)"),
    from_date: str | None = Query(None, description="Начало диапазона дат created_at (ISO)"),
    to_date: str | None = Query(None, description="Конец диапазона дат created_at (ISO)"),
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    VAL-01 / CORE-03 / ADM-02: Список контактов для модерации. Расшифровка ПДн на лету.
    Фильтры: entrance, premise_id, premises_number, status, ip, from_date, to_date.
    """
    clauses = []
    params: dict[str, Any] = {}
    if entrance:
        clauses.append("p.entrance = :entrance")
        params["entrance"] = entrance.strip()
    if premise_id:
        clauses.append("c.premise_id = :pid")
        params["pid"] = premise_id
    if premises_number:
        clauses.append("TRIM(COALESCE(p.premises_number, '')) = :pn")
        params["pn"] = premises_number.strip()
    if status:
        clauses.append("c.status = :st")
        params["st"] = status
    if ip:
        clauses.append("c.ip = :ip")
        params["ip"] = ip.strip()
    if from_date:
        clauses.append("c.created_at >= :from_ts")
        params["from_ts"] = from_date.strip()
    if to_date:
        to_val = to_date.strip()
        if len(to_val) == 10:
            to_val = f"{to_val}T23:59:59.999999"
        clauses.append("c.created_at <= :to_ts")
        params["to_ts"] = to_val
    where = (" AND ".join(clauses)) if clauses else "1=1"

    with get_db() as db:
        rows = db.execute(
            text(
                f"SELECT c.id, c.premise_id, c.is_owner, c.phone, c.email, c.telegram_id, c.how_to_address, "
                f"c.registered_in_ed, c.status, c.created_at, c.updated_at, c.ip, "
                f"p.entrance, p.floor, p.premises_type, p.premises_number, "
                f"o.barrier_vote, o.vote_format "
                f"FROM contacts c "
                f"LEFT JOIN premises p ON p.cadastral_number = c.premise_id "
                f"LEFT JOIN oss_voting o ON o.contact_id = c.id "
                f"WHERE {where} "
                f"ORDER BY p.premises_type NULLS LAST, "
                f"(NULLIF(TRIM(REGEXP_REPLACE(COALESCE(p.premises_number, ''), '[^0-9].*', '')), '')::int) NULLS LAST, "
                f"p.premises_number NULLS LAST, c.id DESC"
            ),
            params,
        ).fetchall()

    items = []
    contact_ids = []
    for r in rows:
        items.append({
            "id": r[0],
            "premise_id": r[1],
            "is_owner": r[2],
            "phone": decrypt(r[3]),
            "email": decrypt(r[4]),
            "telegram_id": decrypt(r[5]),
            "how_to_address": decrypt(r[6]),
            "registered_ed": r[7],
            "status": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
            "updated_at": r[10].isoformat() if r[10] else None,
            "ip": r[11],
            "entrance": r[12],
            "floor": r[13],
            "premises_type": r[14],
            "premises_number": r[15],
            "barrier_vote": r[16],
            "vote_format": r[17],
        })
        contact_ids.append(str(r[0]))

    # Canary: подмешать watermark по этому подъезду и админу; при отсутствии записи — создать при первом просмотре списка.
    # Канареечный контакт подчиняется тем же фильтрам, что и остальные записи (premises_number, premise_id, status;
    # при активных ip/from_date/to_date не показываем — у канарейки нет ip/created_at).
    if entrance and payload.get("sub"):
        entrance_clean = entrance.strip()
        with get_db() as db_canary:
            w = db_canary.execute(
                text(
                    "SELECT premise_id, phone, canary_telegram_id, how_to_address, created_at "
                    "FROM export_watermarks "
                    "WHERE admin_telegram_id = :aid AND entrance = :e "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"aid": payload.get("sub"), "e": entrance_clean},
            ).fetchone()
        if not w:
            w_dict = create_watermark(payload.get("sub"), entrance_clean)
            if w_dict:
                w = (w_dict["premise_id"], w_dict["phone"], w_dict["canary_telegram_id"], w_dict["how_to_address"], w_dict.get("created_at"))
        if w:
            with get_db() as db_prem:
                prem = db_prem.execute(
                    text(
                        "SELECT entrance, floor, premises_type, premises_number "
                        "FROM premises WHERE cadastral_number = :pid"
                    ),
                    {"pid": w[0]},
                ).fetchone()
            show_canary = True
            if premises_number and (prem is None or (prem[3] or "").strip() != premises_number.strip()):
                show_canary = False
            if premise_id and w[0] != premise_id:
                show_canary = False
            if status and status != "pending":
                show_canary = False
            if ip or from_date or to_date:
                show_canary = False
            if show_canary:
                canary_item = {
                    "id": -1,
                    "premise_id": w[0],
                    "is_owner": True,
                    "phone": w[1],
                    "email": None,
                    "telegram_id": w[2],
                    "how_to_address": w[3],
                    "registered_ed": None,
                    "status": "pending",
                    "created_at": w[4].isoformat() if len(w) > 4 and w[4] and hasattr(w[4], "isoformat") else (w[4] if len(w) > 4 and w[4] else None),
                    "updated_at": None,
                    "ip": None,
                    "entrance": prem[0] if prem else None,
                    "floor": prem[1] if prem else None,
                    "premises_type": prem[2] if prem else None,
                    "premises_number": prem[3] if prem else None,
                    "barrier_vote": None,
                    "vote_format": None,
                    "is_canary": True,
                }
                items.append(canary_item)
                items.sort(key=lambda x: (x.get("premises_type") or "", x.get("premises_number") or ""))

    # BE-03 / SR-BE03-004: логируем факт просмотра списка контактов (в т.ч. при пустом результате)
    # entity_id в audit_log ограничен 128 символами — при длинном списке пишем list(N)
    _AUDIT_ENTITY_ID_MAX = 128
    if contact_ids:
        eid = ",".join(contact_ids)
        if len(eid) > _AUDIT_ENTITY_ID_MAX:
            eid = f"list({len(contact_ids)})"
    else:
        eid = "list"
    admin_id = payload.get("sub")
    client_ip = get_client_ip(request)
    with get_db() as db2:
        _audit_log(db2, "contact", eid, "select", None, None, admin_id, client_ip)
        db2.commit()

    return {"contacts": items, "total": len(items)}


@router.get("/contacts/{contact_id}")
def get_contact(
    contact_id: int,
    request: Request,
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """Получить один контакт по ID с расшифровкой ПДн (для формы редактирования)."""
    with get_db() as db:
        r = db.execute(
            text(
                "SELECT c.id, c.premise_id, c.is_owner, c.phone, c.email, c.telegram_id, c.how_to_address, "
                "c.registered_in_ed, c.status, c.created_at, c.updated_at, "
                "p.entrance, p.floor, p.premises_type, p.premises_number, "
                "o.barrier_vote, o.vote_format "
                "FROM contacts c "
                "LEFT JOIN premises p ON p.cadastral_number = c.premise_id "
                "LEFT JOIN oss_voting o ON o.contact_id = c.id "
                "WHERE c.id = :cid"
            ),
            {"cid": contact_id},
        ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Контакт не найден")

    # BE-03 / SR-BE03-004: логируем факт чтения одного контакта
    admin_id = payload.get("sub")
    client_ip = get_client_ip(request)
    with get_db() as db2:
        _audit_log(db2, "contact", str(contact_id), "select", None, None, admin_id, client_ip)
        db2.commit()

    return {
        "id": r[0], "premise_id": r[1], "is_owner": r[2],
        "phone": decrypt(r[3]), "email": decrypt(r[4]), "telegram_id": decrypt(r[5]),
        "how_to_address": decrypt(r[6]),
        "registered_ed": r[7], "status": r[8],
        "created_at": r[9].isoformat() if r[9] else None,
        "updated_at": r[10].isoformat() if r[10] else None,
        "entrance": r[11], "floor": r[12], "premises_type": r[13], "premises_number": r[14],
        "barrier_vote": r[15], "vote_format": r[16],
    }


class AdminContactBody(BaseModel):
    premise_id: str = Field(..., description="Кадастровый номер помещения (cadastral_number)")
    is_owner: bool = Field(True, description="Собственник (true) или проживающий (false)")
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    how_to_address: str | None = Field(None, description="Обращение (как обращаться к жителю/собственнику)")
    barrier_vote: str | None = Field(None, description="for | against | undecided")
    vote_format: str | None = Field(None, description="electronic | paper | undecided")
    registered_ed: str | None = Field(None, description="yes | no")


def _resolve_premise_cadastral(premise_id: str, db) -> str | None:
    """Проверить существование помещения по кадастровому номеру; вернуть cadastral_number или None."""
    r = db.execute(
        text("SELECT 1 FROM premises WHERE cadastral_number = :cn"),
        {"cn": premise_id},
    ).fetchone()
    return premise_id if r else None


@router.post("/contacts")
def create_contact(
    body: AdminContactBody,
    request: Request,
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    ADM-03: Создать контакт от имени администратора. Статус автоматически «валидирован».
    Капча не требуется; применяется валидация форматов (CORE-02), шифрование (BE-02).
    """
    if not body.phone and not body.email and not body.telegram_id:
        raise HTTPException(status_code=400, detail="Укажите хотя бы один контакт: телефон, email или Telegram")
    ok, err = validate_phone(body.phone)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    ok, err = validate_email(body.email)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    ok, err = validate_telegram_id(body.telegram_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    with get_db() as db:
        cadastral = _resolve_premise_cadastral(body.premise_id, db)
        if not cadastral:
            raise HTTPException(status_code=404, detail="Помещение не найдено")

        phone_enc = encrypt(body.phone) if body.phone else None
        email_enc = encrypt(body.email) if body.email else None
        telegram_id_enc = encrypt(body.telegram_id) if body.telegram_id else None
        how_enc = encrypt(body.how_to_address) if body.how_to_address else None
        phone_idx = blind_index_phone(body.phone) if body.phone else None
        email_idx = blind_index_email(body.email) if body.email else None
        telegram_id_idx = blind_index_telegram_id(body.telegram_id) if body.telegram_id else None

        db.execute(
            text(
                "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, how_to_address, "
                "phone_idx, email_idx, telegram_id_idx, registered_in_ed, status, ip) "
                "VALUES (:pid, :io, :phone, :email, :tg, :how, :pi, :ei, :ti, :re, 'validated', :ip)"
            ),
            {
                "pid": cadastral, "io": body.is_owner,
                "phone": phone_enc, "email": email_enc, "tg": telegram_id_enc, "how": how_enc,
                "pi": phone_idx, "ei": email_idx, "ti": telegram_id_idx,
                "re": body.registered_ed,
                "ip": None,
            },
        )
        db.flush()
        r = db.execute(text("SELECT id FROM contacts WHERE premise_id = :pid ORDER BY id DESC LIMIT 1"), {"pid": cadastral}).fetchone()
        contact_id = r[0] if r else None
        if contact_id:
            db.execute(
                text("INSERT INTO oss_voting (contact_id, barrier_vote, vote_format, voted) VALUES (:cid, :bv, :vf, false)"),
                {"cid": contact_id, "bv": body.barrier_vote, "vf": body.vote_format},
            )
        # BE-03 / SR-BE03-001: логируем INSERT контакта
        _audit_log(db, "contact", str(contact_id), "insert", None, None, payload.get("sub"), get_client_ip(request))
        db.commit()

    logger.info("ADM-03: contact created by sub=%s premise_id=%s contact_id=%s", payload.get("sub"), cadastral, contact_id)
    return {"contact_id": contact_id, "status": "validated"}


class AdminContactUpdateBody(BaseModel):
    is_owner: bool = Field(True, description="Собственник (true) или проживающий (false)")
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    how_to_address: str | None = Field(None, description="Обращение (как обращаться к жителю/собственнику)")
    barrier_vote: str | None = Field(None, description="for | against | undecided")
    vote_format: str | None = Field(None, description="electronic | paper | undecided")
    registered_ed: str | None = Field(None, description="yes | no")


@router.put("/contacts/{contact_id}")
def update_contact(
    contact_id: int,
    body: AdminContactUpdateBody,
    request: Request,
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """Обновить контакт (все поля, кроме premise_id и status)."""
    if not body.phone and not body.email and not body.telegram_id:
        raise HTTPException(status_code=400, detail="Укажите хотя бы один контакт: телефон, email или Telegram")
    ok, err = validate_phone(body.phone)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    ok, err = validate_email(body.email)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    ok, err = validate_telegram_id(body.telegram_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    client_ip = get_client_ip(request)
    admin_id = payload.get("sub")

    with get_db() as db:
        row = db.execute(text("SELECT id FROM contacts WHERE id = :cid"), {"cid": contact_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Контакт не найден")

        phone_enc = encrypt(body.phone) if body.phone else None
        email_enc = encrypt(body.email) if body.email else None
        telegram_id_enc = encrypt(body.telegram_id) if body.telegram_id else None
        how_enc = encrypt(body.how_to_address) if (body.how_to_address or "").strip() else None
        phone_idx = blind_index_phone(body.phone) if body.phone else None
        email_idx = blind_index_email(body.email) if body.email else None
        telegram_id_idx = blind_index_telegram_id(body.telegram_id) if body.telegram_id else None

        db.execute(
            text(
                "UPDATE contacts SET is_owner = :io, phone = :phone, email = :email, telegram_id = :tg, how_to_address = :how, "
                "phone_idx = :pi, email_idx = :ei, telegram_id_idx = :ti, "
                "registered_in_ed = :re, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"
            ),
            {
                "io": body.is_owner,
                "phone": phone_enc, "email": email_enc, "tg": telegram_id_enc, "how": how_enc,
                "pi": phone_idx, "ei": email_idx, "ti": telegram_id_idx,
                "re": body.registered_ed, "cid": contact_id,
            },
        )
        # Обновить oss_voting
        oss = db.execute(text("SELECT 1 FROM oss_voting WHERE contact_id = :cid"), {"cid": contact_id}).fetchone()
        if oss:
            db.execute(
                text("UPDATE oss_voting SET barrier_vote = :bv, vote_format = :vf WHERE contact_id = :cid"),
                {"bv": body.barrier_vote, "vf": body.vote_format, "cid": contact_id},
            )
        else:
            db.execute(
                text("INSERT INTO oss_voting (contact_id, barrier_vote, vote_format, voted) VALUES (:cid, :bv, :vf, false)"),
                {"cid": contact_id, "bv": body.barrier_vote, "vf": body.vote_format},
            )
        _audit_log(db, "contact", str(contact_id), "update", None, None, admin_id, client_ip)
        db.commit()

    logger.info("ADM-03: contact updated id=%s by sub=%s", contact_id, admin_id)
    return {"contact_id": contact_id, "updated": True}


class StatusBody(BaseModel):
    status: str = Field(..., description="validated | inactive")


class BulkStatusBody(BaseModel):
    contact_ids: list[int] = Field(..., description="Список ID контактов")
    status: str = Field(..., description="pending | validated | inactive")


def _audit_log(db, entity_type: str, entity_id: str, action: str, old_value: str | None, new_value: str | None, user_id: str | None, ip: str | None) -> None:
    """VAL-01-005: запись в аудит-лог (BE-03)."""
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


@router.patch("/contacts/bulk-status")
def bulk_update_status(
    body: BulkStatusBody,
    request: Request,
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    CORE-03 / SR-CORE03-001: Массовая смена статуса контактов.
    Принимает список ID и целевой статус.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="status должен быть 'pending', 'validated' или 'inactive'")
    if not body.contact_ids:
        raise HTTPException(status_code=400, detail="Список ID не может быть пустым")
    if len(body.contact_ids) > 200:
        raise HTTPException(status_code=400, detail="Максимум 200 контактов за раз")

    client_ip = get_client_ip(request)
    admin_id = payload.get("sub")
    updated = 0

    with get_db() as db:
        for cid in body.contact_ids:
            row = db.execute(
                text("SELECT id, status FROM contacts WHERE id = :cid"),
                {"cid": cid},
            ).fetchone()
            if not row:
                continue
            old_status = row[1]
            if old_status == body.status:
                continue
            db.execute(
                text("UPDATE contacts SET status = :st, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"),
                {"st": body.status, "cid": cid},
            )
            _audit_log(db, "contact", str(cid), "status_change", old_status, body.status, admin_id, client_ip)
            updated += 1
        db.commit()

    logger.info("CORE-03: bulk status -> %s for %d contacts by sub=%s", body.status, updated, admin_id)
    return {"updated": updated, "status": body.status}


@router.patch("/contacts/{contact_id}/status")
def update_contact_status(
    contact_id: int,
    body: StatusBody,
    request: Request,
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    VAL-01: Установка статуса контакта «валидирован» или «неактуальный».
    Доступ только для administrator/super_administrator. SR-VAL01-001, SR-VAL01-002.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="status must be 'validated' or 'inactive'")
    client_ip = get_client_ip(request)
    admin_id = payload.get("sub")

    with get_db() as db:
        row = db.execute(
            text("SELECT id, status FROM contacts WHERE id = :cid"),
            {"cid": contact_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Контакт не найден")
        old_status = row[1]
        if old_status == body.status:
            return {"contact_id": contact_id, "status": body.status}
        db.execute(
            text("UPDATE contacts SET status = :st, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"),
            {"st": body.status, "cid": contact_id},
        )
        _audit_log(db, "contact", str(contact_id), "status_change", old_status, body.status, admin_id, client_ip)
        db.commit()

    logger.info("VAL-01: contact_id=%s status %s -> %s by sub=%s", contact_id, old_status, body.status, admin_id)
    return {"contact_id": contact_id, "status": body.status}