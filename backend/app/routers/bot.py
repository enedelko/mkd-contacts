"""
BOT-01..04: API for Telegram bot.
All endpoints require X-Bot-Token (shared secret).
Reuses crypto, submit_service, validators, bot_premise_resolver.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth_bot import require_bot_token
from app.bot_premise_resolver import resolve as resolve_premise
from app.crypto import (
    blind_index_phone,
    blind_index_telegram_id,
    decrypt,
    encrypt,
)
from app.db import get_db
from app.rate_limit import check_bot_rate_limit
from app.submit_service import _audit_log, _count_pending_on_premise, PENDING_LIMIT_PER_PREMISE
from app.validators import validate_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["bot"], dependencies=[Depends(require_bot_token)])

BOT_RATE_LIMIT = 10


class ResolveBody(BaseModel):
    text: str = Field(..., max_length=100)
    telegram_user_id: str | None = None


class PremiseBody(BaseModel):
    telegram_user_id: str
    premise_id: str


class AnswersBody(BaseModel):
    telegram_user_id: str
    vote_format: str | None = None
    registered_in_ed: str | None = None
    barrier_vote: str | None = None
    phone: str | None = Field(None, description="Phone or null to delete")


class ForgetBody(BaseModel):
    telegram_user_id: str


def _find_contacts_by_tg(db, tg_idx: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT c.id, c.premise_id, p.premises_type, p.premises_number "
            "FROM contacts c JOIN premises p ON p.cadastral_number = c.premise_id "
            "WHERE c.telegram_id_idx = :idx AND c.status IN ('pending', 'validated')"
        ),
        {"idx": tg_idx},
    ).fetchall()
    return [{"id": r[0], "premise_id": r[1], "type": r[2], "number": r[3]} for r in rows]


def _get_short_names(db) -> dict[str, str]:
    rows = db.execute(
        text("SELECT DISTINCT premises_type, short_name FROM premise_type_aliases")
    ).fetchall()
    return {r[0]: r[1] for r in rows}


@router.post("/resolve-premise")
def resolve_premise_endpoint(body: ResolveBody) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(body.telegram_user_id) if body.telegram_user_id else None
    matches = resolve_premise(body.text, tg_idx)
    return {"matches": matches}


@router.post("/premises", status_code=201)
def add_premise(body: PremiseBody) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(body.telegram_user_id)
    if not tg_idx:
        raise HTTPException(status_code=400, detail="telegram_user_id required")

    allowed, retry_after = check_bot_rate_limit(tg_idx, BOT_RATE_LIMIT)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry_after)})

    with get_db() as db:
        premise = db.execute(
            text("SELECT cadastral_number FROM premises WHERE cadastral_number = :cn"),
            {"cn": body.premise_id},
        ).fetchone()
        if not premise:
            raise HTTPException(status_code=404, detail="Premise not found")

        if _count_pending_on_premise(db, body.premise_id) >= PENDING_LIMIT_PER_PREMISE:
            raise HTTPException(status_code=409, detail="Premise limit exceeded")

        existing = db.execute(
            text(
                "SELECT id FROM contacts "
                "WHERE premise_id = :pid AND telegram_id_idx = :idx AND status IN ('pending', 'validated')"
            ),
            {"pid": body.premise_id, "idx": tg_idx},
        ).fetchone()
        if existing:
            return {"detail": "Already linked", "contact_id": existing[0]}

        tg_enc = encrypt(body.telegram_user_id)
        db.execute(
            text(
                "INSERT INTO contacts (premise_id, is_owner, telegram_id, telegram_id_idx, "
                "consent_version, status, source) "
                "VALUES (:pid, true, :tg, :tg_idx, '1.0', 'pending', 'telegram')"
            ),
            {"pid": body.premise_id, "tg": tg_enc, "tg_idx": tg_idx},
        )
        db.flush()
        cid = db.execute(
            text("SELECT id FROM contacts WHERE premise_id = :pid AND telegram_id_idx = :idx ORDER BY id DESC LIMIT 1"),
            {"pid": body.premise_id, "idx": tg_idx},
        ).scalar()
        if cid:
            db.execute(
                text("INSERT INTO oss_voting (contact_id, barrier_vote, vote_format, voted) VALUES (:cid, NULL, NULL, false)"),
                {"cid": cid},
            )
            _audit_log(db, "contact", str(cid), "insert", None, "source=telegram", None, None)
        db.commit()
        return {"detail": "Premise linked", "contact_id": cid}


@router.delete("/me/premises/{premise_id}")
def remove_premise(premise_id: str, body: PremiseBody) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(body.telegram_user_id)
    if not tg_idx:
        raise HTTPException(status_code=400, detail="telegram_user_id required")

    with get_db() as db:
        row = db.execute(
            text(
                "SELECT id FROM contacts "
                "WHERE premise_id = :pid AND telegram_id_idx = :idx AND status IN ('pending', 'validated')"
            ),
            {"pid": premise_id, "idx": tg_idx},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")

        cid = row[0]
        db.execute(
            text(
                "UPDATE contacts SET status = 'inactive', phone = NULL, email = NULL, "
                "telegram_id = NULL, how_to_address = NULL, phone_idx = NULL, email_idx = NULL, "
                "telegram_id_idx = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"
            ),
            {"cid": cid},
        )
        _audit_log(db, "contact", str(cid), "premise_removed", None, None, None, None)
        db.commit()
    return {"detail": "Premise removed"}


@router.patch("/me/answers")
def update_answers(body: AnswersBody) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(body.telegram_user_id)
    if not tg_idx:
        raise HTTPException(status_code=400, detail="telegram_user_id required")

    allowed, retry_after = check_bot_rate_limit(tg_idx, BOT_RATE_LIMIT)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry_after)})

    if body.phone is not None and body.phone != "":
        ok, err = validate_phone(body.phone)
        if not ok:
            raise HTTPException(status_code=400, detail=err or "Invalid phone")

    with get_db() as db:
        contacts = _find_contacts_by_tg(db, tg_idx)
        if not contacts:
            raise HTTPException(status_code=404, detail="No contacts found")

        for c in contacts:
            updates = []
            params: dict[str, Any] = {"cid": c["id"]}

            if body.phone is not None:
                if body.phone == "":
                    updates.extend(["phone = NULL", "phone_idx = NULL"])
                else:
                    updates.extend(["phone = :phone", "phone_idx = :phone_idx"])
                    params["phone"] = encrypt(body.phone)
                    params["phone_idx"] = blind_index_phone(body.phone)

            if body.registered_in_ed is not None:
                updates.append("registered_in_ed = :re")
                # Бот присылает "true"/"false"; в БД и шахматке везде используется yes/no
                re_val = body.registered_in_ed
                if re_val in ("true", True):
                    params["re"] = "yes"
                elif re_val in ("false", False):
                    params["re"] = "no"
                else:
                    params["re"] = re_val

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                db.execute(text(f"UPDATE contacts SET {', '.join(updates)} WHERE id = :cid"), params)

            if body.vote_format is not None or body.barrier_vote is not None:
                oss = db.execute(
                    text("SELECT vote_format, barrier_vote FROM oss_voting WHERE contact_id = :cid"),
                    {"cid": c["id"]},
                ).fetchone()
                vf = body.vote_format if body.vote_format is not None else (oss[0] if oss else None)
                bv = body.barrier_vote if body.barrier_vote is not None else (oss[1] if oss else None)
                if oss:
                    db.execute(
                        text("UPDATE oss_voting SET vote_format = :vf, barrier_vote = :bv WHERE contact_id = :cid"),
                        {"vf": vf, "bv": bv, "cid": c["id"]},
                    )
                else:
                    db.execute(
                        text("INSERT INTO oss_voting (contact_id, vote_format, barrier_vote, voted) VALUES (:cid, :vf, :bv, false)"),
                        {"cid": c["id"], "vf": vf, "bv": bv},
                    )

        _audit_log(db, "contact", tg_idx, "bot_answers_update", None, None, None, None)
        db.commit()
    return {"detail": "Answers updated"}


@router.get("/me/data")
def get_my_data(telegram_user_id: str) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(telegram_user_id)
    if not tg_idx:
        raise HTTPException(status_code=400, detail="telegram_user_id required")

    with get_db() as db:
        short_names = _get_short_names(db)
        contacts = _find_contacts_by_tg(db, tg_idx)
        if not contacts:
            return {"premises": [], "vote_format": None, "registered_in_ed": None, "barrier_vote": None, "phone": None}

        premises = []
        for c in contacts:
            short = short_names.get(c["type"], c["type"])
            premises.append({
                "premise_id": c["premise_id"],
                "display": f"{c['type']} {c['number']}",
                "short_display": f"{short} {c['number']}",
            })

        first = contacts[0]
        oss = db.execute(
            text("SELECT vote_format, barrier_vote FROM oss_voting WHERE contact_id = :cid"),
            {"cid": first["id"]},
        ).fetchone()

        # Телефон может быть в любом из контактов пользователя (напр. добавлен через веб в одном, бот создал другой без телефона)
        contact_ids = [c["id"] for c in contacts]
        phone = None
        for cid in contact_ids:
            phone_row = db.execute(
                text("SELECT phone FROM contacts WHERE id = :cid AND phone IS NOT NULL AND trim(phone) != ''"),
                {"cid": cid},
            ).fetchone()
            if phone_row and phone_row[0]:
                phone = decrypt(phone_row[0])
                break

        reg_ed = db.execute(
            text("SELECT registered_in_ed FROM contacts WHERE id = :cid"),
            {"cid": first["id"]},
        ).scalar()

    return {
        "premises": premises,
        "vote_format": oss[0] if oss else None,
        "registered_in_ed": reg_ed,
        "barrier_vote": oss[1] if oss else None,
        "phone": phone,
    }


@router.delete("/me/forget")
def forget(body: ForgetBody) -> dict[str, Any]:
    tg_idx = blind_index_telegram_id(body.telegram_user_id)
    if not tg_idx:
        raise HTTPException(status_code=400, detail="telegram_user_id required")

    with get_db() as db:
        contacts = _find_contacts_by_tg(db, tg_idx)
        if not contacts:
            return {"detail": "No data found"}

        for c in contacts:
            db.execute(
                text(
                    "UPDATE contacts SET status = 'inactive', phone = NULL, email = NULL, "
                    "telegram_id = NULL, how_to_address = NULL, phone_idx = NULL, email_idx = NULL, "
                    "telegram_id_idx = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = :cid"
                ),
                {"cid": c["id"]},
            )

        _audit_log(db, "contact", tg_idx, "forget", None, None, None, None)
        db.commit()
    return {"detail": "All data deleted"}
