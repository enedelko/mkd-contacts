"""
ADM-03: POST /api/admin/contacts — добавление контакта админом.
VAL-01: PATCH /api/admin/contacts/{contact_id}/status — смена статуса контакта (validated/inactive).
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from sqlalchemy import text

from app.db import get_db
from app.jwt_utils import require_admin
from app.crypto import encrypt, blind_index_phone, blind_index_email, blind_index_telegram_id
from app.validators import validate_phone, validate_email, validate_telegram_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_STATUSES = ("validated", "inactive")


class AdminContactBody(BaseModel):
    premise_id: str = Field(..., description="Кадастровый номер помещения (cadastral_number)")
    is_owner: bool = Field(True, description="Собственник (true) или проживающий (false)")
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
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
    payload: dict = Depends(require_admin),
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
        phone_idx = blind_index_phone(body.phone) if body.phone else None
        email_idx = blind_index_email(body.email) if body.email else None
        telegram_id_idx = blind_index_telegram_id(body.telegram_id) if body.telegram_id else None

        db.execute(
            text(
                "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, phone_idx, email_idx, telegram_id_idx, "
                "registered_in_ed, status, ip) VALUES (:pid, :io, :phone, :email, :tg, :pi, :ei, :ti, :re, 'validated', :ip)"
            ),
            {
                "pid": cadastral, "io": body.is_owner,
                "phone": phone_enc, "email": email_enc, "tg": telegram_id_enc,
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
        db.commit()

    logger.info("ADM-03: contact created by sub=%s premise_id=%s contact_id=%s", payload.get("sub"), cadastral, contact_id)
    return {"contact_id": contact_id, "status": "validated"}


class StatusBody(BaseModel):
    status: str = Field(..., description="validated | inactive")


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


@router.patch("/contacts/{contact_id}/status")
def update_contact_status(
    contact_id: int,
    body: StatusBody,
    request: Request,
    payload: dict = Depends(require_admin),
) -> dict[str, Any]:
    """
    VAL-01: Установка статуса контакта «валидирован» или «неактуальный».
    Доступ только для administrator/super_administrator. SR-VAL01-001, SR-VAL01-002.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="status must be 'validated' or 'inactive'")
    client_ip = request.client.host if request.client else None
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