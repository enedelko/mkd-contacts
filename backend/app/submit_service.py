"""
FE-04, CORE-02: приём анкеты (POST /api/submit).
Валидация, лимит 10 pending на помещение, дедупликация по Blind Index, капча (Turnstile), шифрование.
"""
import logging
from typing import Any

from sqlalchemy import text

from app.crypto import (
    blind_index_email,
    blind_index_phone,
    blind_index_telegram_id,
    encrypt,
)
from app.db import get_db
from app.import_register import _find_contact_by_indexes, _collision
from app.validators import validate_phone, validate_email, validate_telegram_id

logger = logging.getLogger(__name__)

PENDING_LIMIT_PER_PREMISE = 10  # SR-CORE02-004
SUBMIT_RATE_LIMIT_PER_HOUR = 10  # FE-04 AF-2: 10 записей/час (по IP)


def _premise_id_from_request(premise_id: str | int, db) -> int | None:
    """Преобразовать premise_id (cadastral_number или id) в premises.id."""
    if isinstance(premise_id, int) or (isinstance(premise_id, str) and premise_id.isdigit()):
        r = db.execute(text("SELECT id FROM premises WHERE id = :id"), {"id": int(premise_id)}).fetchone()
        return r[0] if r else None
    r = db.execute(text("SELECT id FROM premises WHERE cadastral_number = :cn"), {"cn": str(premise_id)}).fetchone()
    return r[0] if r else None


def _count_pending_on_premise(db, premise_db_id: int) -> int:
    """Количество контактов со статусом pending по помещению (SR-CORE02-004)."""
    r = db.execute(
        text("SELECT COUNT(*) FROM contacts WHERE premise_id = :pid AND status = 'pending'"),
        {"pid": premise_db_id},
    ).fetchone()
    return r[0] or 0


def submit_questionnaire(
    premise_id: str | int,
    is_owner: bool,
    phone: str | None,
    email: str | None,
    telegram_id: str | None,
    vote_for: bool,
    vote_format: str,
    registered_ed: bool,
    consent_version: str | None,
    client_ip: str | None,
    captcha_verified: bool = True,
) -> dict[str, Any]:
    """
    Обработать анкету: валидация, лимиты, дедупликация, сохранение.
    Возвращает dict: success, message или error с detail/errors/code.
    """
    if not phone and not email and not telegram_id:
        return {"success": False, "detail": "At least one of phone, email, telegram_id required", "errors": [{"field": "contact", "message": "At least one contact field required"}]}

    ok, err = validate_phone(phone)
    if not ok:
        return {"success": False, "detail": "Validation failed", "errors": [{"field": "phone", "message": err}]}
    ok, err = validate_email(email)
    if not ok:
        return {"success": False, "detail": "Validation failed", "errors": [{"field": "email", "message": err}]}
    ok, err = validate_telegram_id(telegram_id)
    if not ok:
        return {"success": False, "detail": "Validation failed", "errors": [{"field": "telegram_id", "message": err}]}

    if not captcha_verified:
        return {"success": False, "detail": "Captcha verification required"}

    with get_db() as db:
        premise_db_id = _premise_id_from_request(premise_id, db)
        if not premise_db_id:
            return {"success": False, "detail": "Premise not found", "code": "PREMISE_NOT_FOUND"}

        if _count_pending_on_premise(db, premise_db_id) >= PENDING_LIMIT_PER_PREMISE:
            return {"success": False, "detail": "Premise limit exceeded: max 10 unvalidated contacts per premise", "code": "PREMISE_LIMIT_EXCEEDED"}

        phone_idx = blind_index_phone(phone) if phone else None
        email_idx = blind_index_email(email) if email else None
        telegram_id_idx = blind_index_telegram_id(telegram_id) if telegram_id else None
        existing = _find_contact_by_indexes(db, premise_db_id, phone_idx, email_idx, telegram_id_idx)

        row = {"phone": phone, "email": email, "telegram_id": telegram_id}
        collision_msg = _collision(existing, row, phone_idx, email_idx, telegram_id_idx)
        if collision_msg:
            return {"success": False, "detail": "Contact data conflict: existing record has different values. Please contact administrators to resolve.", "code": "CONTACT_CONFLICT"}

        phone_enc = encrypt(phone)
        email_enc = encrypt(email)
        telegram_id_enc = encrypt(telegram_id)

        def _upsert_oss_voting(cid: int):
            r = db.execute(text("SELECT 1 FROM oss_voting WHERE contact_id = :cid"), {"cid": cid}).fetchone()
            if r:
                db.execute(
                    text("UPDATE oss_voting SET position_for = :pf, vote_format = :vf, voted_in_ed = :ve WHERE contact_id = :cid"),
                    {"pf": str(vote_for).lower(), "vf": vote_format, "ve": registered_ed, "cid": cid},
                )
            else:
                db.execute(
                    text("INSERT INTO oss_voting (contact_id, position_for, vote_format, voted_in_ed, voted) VALUES (:cid, :pf, :vf, :ve, false)"),
                    {"cid": cid, "pf": str(vote_for).lower(), "vf": vote_format, "ve": registered_ed},
                )

        if existing:
            same_phone = (existing.get("phone_idx") == phone_idx) or (not phone_idx and not existing.get("has_phone"))
            same_email = (existing.get("email_idx") == email_idx) or (not email_idx and not existing.get("has_email"))
            same_tg = (existing.get("telegram_id_idx") == telegram_id_idx) or (not telegram_id_idx and not existing.get("has_telegram_id"))
            if same_phone and same_email and same_tg:
                db.execute(text("UPDATE contacts SET updated_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": existing["id"]})
                _upsert_oss_voting(existing["id"])
                db.commit()
                logger.info("Submit: updated contact id=%s premise_id=%s", existing["id"], premise_db_id)
                return {"success": True, "message": "Данные приняты"}
            need_enrich = []
            params = {"cid": existing["id"]}
            if email_enc and not existing.get("has_email"):
                need_enrich.append("email = :email"); need_enrich.append("email_idx = :email_idx"); params["email"] = email_enc; params["email_idx"] = email_idx
            if phone_enc and not existing.get("has_phone"):
                need_enrich.append("phone = :phone"); need_enrich.append("phone_idx = :phone_idx"); params["phone"] = phone_enc; params["phone_idx"] = phone_idx
            if telegram_id_enc and not existing.get("has_telegram_id"):
                need_enrich.append("telegram_id = :telegram_id"); need_enrich.append("telegram_id_idx = :telegram_id_idx"); params["telegram_id"] = telegram_id_enc; params["telegram_id_idx"] = telegram_id_idx
            if need_enrich:
                set_clause = ", ".join(need_enrich) + ", updated_at = CURRENT_TIMESTAMP"
                db.execute(text("UPDATE contacts SET " + set_clause + " WHERE id = :cid"), params)
            _upsert_oss_voting(existing["id"])
            db.commit()
            logger.info("Submit: enriched contact id=%s premise_id=%s", existing["id"], premise_db_id)
            return {"success": True, "message": "Данные приняты"}
        else:
            db.execute(
                text(
                    "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, phone_idx, email_idx, telegram_id_idx, registered_in_ed, consent_version, status, ip) "
                    "VALUES (:pid, :io, :phone, :email, :tg, :pi, :ei, :ti, :re, :cv, 'pending', :ip)"
                ),
                {
                    "pid": premise_db_id, "io": is_owner,
                    "phone": phone_enc, "email": email_enc, "telegram_id": telegram_id_enc,
                    "pi": phone_idx, "ei": email_idx, "ti": telegram_id_idx,
                    "re": registered_ed, "cv": consent_version, "ip": client_ip,
                },
            )
            db.flush()
            contact_id_row = db.execute(text("SELECT id FROM contacts WHERE premise_id = :pid ORDER BY id DESC LIMIT 1"), {"pid": premise_db_id}).fetchone()
            contact_id = contact_id_row[0] if contact_id_row else None
            if contact_id:
                db.execute(
                    text("INSERT INTO oss_voting (contact_id, position_for, vote_format, voted_in_ed, voted) VALUES (:cid, :pf, :vf, :ve, false)"),
                    {"cid": contact_id, "pf": str(vote_for).lower(), "vf": vote_format, "ve": registered_ed},
                )
            db.commit()
            logger.info("Submit: new contact premise_id=%s (no PII in log)", premise_db_id)
            return {"success": True, "message": "Данные приняты"}
