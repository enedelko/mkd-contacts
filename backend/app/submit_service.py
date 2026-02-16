"""
FE-04, CORE-02: приём анкеты (POST /api/submit).
Валидация, лимит 10 pending на помещение, дедупликация по Blind Index, капча (Turnstile), шифрование.
"""
import logging
from typing import Any

from sqlalchemy import text

from sqlalchemy import text as sa_text

from app.crypto import (
    blind_index_email,
    blind_index_phone,
    blind_index_telegram_id,
    encrypt,
)
from app.db import get_db
from app.import_register import _find_contact_by_indexes, _collision
from app.validators import validate_phone, validate_email, validate_telegram_id


def _audit_log(db, entity_type: str, entity_id: str, action: str, old_value: str | None, new_value: str | None, user_id: str | None, ip: str | None) -> None:
    """BE-03: запись в аудит-лог."""
    try:
        db.execute(
            sa_text(
                "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user_id, ip) "
                "VALUES (:et, :eid, :act, :old, :new, :uid, :ip)"
            ),
            {"et": entity_type, "eid": entity_id, "act": action, "old": old_value, "new": new_value, "uid": user_id, "ip": ip},
        )
    except Exception as e:
        logger.warning("audit_log insert failed: %s", e)

logger = logging.getLogger(__name__)

PENDING_LIMIT_PER_PREMISE = 10  # SR-CORE02-004
SUBMIT_RATE_LIMIT_PER_HOUR = 10  # FE-04 AF-2: 10 записей/час (по IP)


def _resolve_premise_cadastral(premise_id: str, db) -> str | None:
    """Проверить существование помещения по кадастровому номеру; вернуть cadastral_number или None."""
    r = db.execute(
        text("SELECT 1 FROM premises WHERE cadastral_number = :cn"),
        {"cn": premise_id},
    ).fetchone()
    return premise_id if r else None


def _count_pending_on_premise(db, premise_id: str) -> int:
    """Количество контактов со статусом pending по помещению (SR-CORE02-004)."""
    r = db.execute(
        text("SELECT COUNT(*) FROM contacts WHERE premise_id = :pid AND status = 'pending'"),
        {"pid": premise_id},
    ).fetchone()
    return r[0] or 0


def submit_questionnaire(
    premise_id: str,
    is_owner: bool,
    phone: str | None,
    email: str | None,
    telegram_id: str | None,
    barrier_vote: str | None,
    vote_format: str | None,
    registered_ed: str | None,
    consent_version: str | None,
    client_ip: str | None,
    captcha_verified: bool = True,
) -> dict[str, Any]:
    """
    Обработать анкету: валидация, лимиты, дедупликация, сохранение.
    Возвращает dict: success, message или error с detail/errors/code.
    """
    has_contact = bool(phone or email or telegram_id)
    has_oss = bool(barrier_vote or vote_format or registered_ed)

    if not has_contact and not has_oss:
        return {"success": False, "detail": "Укажите контакт или ответьте на вопросы по предстоящему ОСС", "errors": [{"field": "contact", "message": "Укажите контакт или ответьте на вопросы по предстоящему ОСС"}]}

    if consent_version not in ("1.0", "IP"):
        return {"success": False, "detail": "Некорректная версия согласия"}
    if has_contact and consent_version != "1.0":
        return {"success": False, "detail": "Необходимо согласие на обработку ПДн", "errors": [{"field": "consent", "message": "Необходимо согласие на обработку ПДн"}]}
    if not has_contact and consent_version != "IP":
        return {"success": False, "detail": "Некорректная версия согласия для анонимной отправки"}

    if has_contact:
        ok, err = validate_phone(phone)
        if not ok:
            return {"success": False, "detail": "Ошибка валидации", "errors": [{"field": "phone", "message": err}]}
        ok, err = validate_email(email)
        if not ok:
            return {"success": False, "detail": "Ошибка валидации", "errors": [{"field": "email", "message": err}]}
        ok, err = validate_telegram_id(telegram_id)
        if not ok:
            return {"success": False, "detail": "Ошибка валидации", "errors": [{"field": "telegram_id", "message": err}]}

    if not captcha_verified:
        return {"success": False, "detail": "Необходимо пройти проверку капчи"}

    with get_db() as db:
        cadastral = _resolve_premise_cadastral(premise_id, db)
        if not cadastral:
            return {"success": False, "detail": "Помещение не найдено", "code": "PREMISE_NOT_FOUND"}

        if _count_pending_on_premise(db, cadastral) >= PENDING_LIMIT_PER_PREMISE:
            return {"success": False, "detail": "Превышен лимит: не более 10 неподтверждённых контактов на помещение", "code": "PREMISE_LIMIT_EXCEEDED"}

        if not has_contact:
            anon_exists = db.execute(
                text("SELECT 1 FROM contacts WHERE premise_id = :pid AND phone IS NULL AND email IS NULL AND telegram_id IS NULL AND status IN ('pending','validated')"),
                {"pid": cadastral},
            ).fetchone()
            if anon_exists:
                return {"success": False, "detail": "Анонимный голос по этому помещению уже зарегистрирован", "code": "ANON_VOTE_EXISTS"}

        phone_idx = blind_index_phone(phone) if phone else None
        email_idx = blind_index_email(email) if email else None
        telegram_id_idx = blind_index_telegram_id(telegram_id) if telegram_id else None
        existing = _find_contact_by_indexes(db, cadastral, phone_idx, email_idx, telegram_id_idx) if has_contact else None

        row = {"phone": phone, "email": email, "telegram_id": telegram_id}
        collision_msg = _collision(existing, row, phone_idx, email_idx, telegram_id_idx)
        if collision_msg:
            return {"success": False, "detail": "Конфликт данных: запись с такими контактами уже существует. Обратитесь к администратору.", "code": "CONTACT_CONFLICT"}

        phone_enc = encrypt(phone)
        email_enc = encrypt(email)
        telegram_id_enc = encrypt(telegram_id)

        def _upsert_oss_voting(cid: int):
            r = db.execute(text("SELECT 1 FROM oss_voting WHERE contact_id = :cid"), {"cid": cid}).fetchone()
            if r:
                db.execute(
                    text("UPDATE oss_voting SET barrier_vote = :bv, vote_format = :vf WHERE contact_id = :cid"),
                    {"bv": barrier_vote, "vf": vote_format, "cid": cid},
                )
            else:
                db.execute(
                    text("INSERT INTO oss_voting (contact_id, barrier_vote, vote_format, voted) VALUES (:cid, :bv, :vf, false)"),
                    {"cid": cid, "bv": barrier_vote, "vf": vote_format},
                )

        if existing:
            contact_status = db.execute(
                text("SELECT status FROM contacts WHERE id = :cid"),
                {"cid": existing["id"]},
            ).scalar()

            if contact_status == "validated" and has_oss:
                admins = db.execute(
                    text("SELECT full_name, premises FROM admins ORDER BY created_at")
                ).fetchall()
                admin_list = [{"full_name": r[0] or "—", "premises": r[1] or "—"} for r in admins]
                return {
                    "success": False,
                    "detail": "Ваш контакт валидирован. Для изменения ответов по ОСС обратитесь к администраторам.",
                    "code": "OSS_LOCKED_VALIDATED",
                    "admins": admin_list,
                }

            same_phone = (existing.get("phone_idx") == phone_idx) or (not phone_idx and not existing.get("has_phone"))
            same_email = (existing.get("email_idx") == email_idx) or (not email_idx and not existing.get("has_email"))
            same_tg = (existing.get("telegram_id_idx") == telegram_id_idx) or (not telegram_id_idx and not existing.get("has_telegram_id"))
            if same_phone and same_email and same_tg:
                db.execute(text("UPDATE contacts SET updated_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": existing["id"]})
                _upsert_oss_voting(existing["id"])
                db.commit()
                logger.info("Submit: updated contact id=%s premise_id=%s", existing["id"], cadastral)
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
            logger.info("Submit: enriched contact id=%s premise_id=%s", existing["id"], cadastral)
            return {"success": True, "message": "Данные приняты"}
        else:
            db.execute(
                text(
                    "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, phone_idx, email_idx, telegram_id_idx, registered_in_ed, consent_version, status, ip) "
                    "VALUES (:pid, :io, :phone, :email, :tg, :pi, :ei, :ti, :re, :cv, 'pending', :ip)"
                ),
                {
                    "pid": cadastral, "io": is_owner,
                    "phone": phone_enc, "email": email_enc, "tg": telegram_id_enc,
                    "pi": phone_idx, "ei": email_idx, "ti": telegram_id_idx,
                    "re": registered_ed, "cv": consent_version, "ip": client_ip,
                },
            )
            db.flush()
            contact_id_row = db.execute(text("SELECT id FROM contacts WHERE premise_id = :pid ORDER BY id DESC LIMIT 1"), {"pid": cadastral}).fetchone()
            contact_id = contact_id_row[0] if contact_id_row else None
            if contact_id:
                db.execute(
                    text("INSERT INTO oss_voting (contact_id, barrier_vote, vote_format, voted) VALUES (:cid, :bv, :vf, false)"),
                    {"cid": contact_id, "bv": barrier_vote, "vf": vote_format},
                )
            # BE-03 / SR-BE03-001: логируем INSERT контакта (публичная форма)
            _audit_log(db, "contact", str(contact_id), "insert", None, None, None, client_ip)
            db.commit()
            logger.info("Submit: new contact premise_id=%s (no PII in log)", cadastral)
            return {"success": True, "message": "Данные приняты"}
