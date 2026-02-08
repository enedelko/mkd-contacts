"""
ADM-03: POST /api/admin/contacts — добавление контакта админом (авто-валидация, статус validated).
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy import text

from app.db import get_db
from app.jwt_utils import require_admin
from app.crypto import encrypt, blind_index_phone, blind_index_email, blind_index_telegram_id
from app.validators import validate_phone, validate_email, validate_telegram_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminContactBody(BaseModel):
    premise_id: str | int = Field(..., description="id помещения или cadastral_number")
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    vote_for: bool = True
    vote_format: str = Field("paper", description="paper | electronic")
    registered_ed: bool = False


def _premise_db_id(premise_id: str | int, db) -> int | None:
    if isinstance(premise_id, int) or (isinstance(premise_id, str) and premise_id.isdigit()):
        r = db.execute(text("SELECT id FROM premises WHERE id = :id"), {"id": int(premise_id)}).fetchone()
        return r[0] if r else None
    r = db.execute(text("SELECT id FROM premises WHERE cadastral_number = :cn"), {"cn": str(premise_id)}).fetchone()
    return r[0] if r else None


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
        raise HTTPException(status_code=400, detail="At least one of phone, email, telegram_id required")
    ok, err = validate_phone(body.phone)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid phone: {err}")
    ok, err = validate_email(body.email)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid email: {err}")
    ok, err = validate_telegram_id(body.telegram_id)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid telegram_id: {err}")

    with get_db() as db:
        premise_db_id = _premise_db_id(body.premise_id, db)
        if not premise_db_id:
            raise HTTPException(status_code=404, detail="Premise not found")

        phone_enc = encrypt(body.phone) if body.phone else None
        email_enc = encrypt(body.email) if body.email else None
        telegram_id_enc = encrypt(body.telegram_id) if body.telegram_id else None
        phone_idx = blind_index_phone(body.phone) if body.phone else None
        email_idx = blind_index_email(body.email) if body.email else None
        telegram_id_idx = blind_index_telegram_id(body.telegram_id) if body.telegram_id else None

        db.execute(
            text(
                "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, phone_idx, email_idx, telegram_id_idx, "
                "registered_in_ed, status, ip) VALUES (:pid, true, :phone, :email, :tg, :pi, :ei, :ti, :re, 'validated', :ip)"
            ),
            {
                "pid": premise_db_id,
                "phone": phone_enc, "email": email_enc, "telegram_id": telegram_id_enc,
                "pi": phone_idx, "ei": email_idx, "ti": telegram_id_idx,
                "re": body.registered_ed,
                "ip": None,
            },
        )
        db.flush()
        r = db.execute(text("SELECT id FROM contacts WHERE premise_id = :pid ORDER BY id DESC LIMIT 1"), {"pid": premise_db_id}).fetchone()
        contact_id = r[0] if r else None
        if contact_id:
            db.execute(
                text("INSERT INTO oss_voting (contact_id, position_for, vote_format, voted_in_ed, voted) VALUES (:cid, :pf, :vf, :ve, false)"),
                {"cid": contact_id, "pf": str(body.vote_for).lower(), "vf": body.vote_format, "ve": body.registered_ed},
            )
        db.commit()

    logger.info("ADM-03: contact created by sub=%s premise_id=%s contact_id=%s", payload.get("sub"), premise_db_id, contact_id)
    return {"contact_id": contact_id, "status": "validated"}