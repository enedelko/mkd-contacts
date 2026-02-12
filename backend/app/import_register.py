"""
CORE-01: Импорт реестра помещений и контактов (CSV/XLS/XLSX).
Парсинг, валидация, сопоставление по Blind Index, шифрование (BE-02), отчёт.
"""
import csv
import io
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
from app.room_normalizer import normalize_room_number

logger = logging.getLogger(__name__)

# Ожидаемые колонки (LOST-02, CORE-01). Минимальный набор для валидации структуры.
REQUIRED_PREMISE_COLUMNS = ["cadastral_number"]
OPTIONAL_PREMISE_COLUMNS = ["area", "entrance", "floor", "premises_type", "premises_number"]
CONTACT_COLUMNS = ["phone", "email", "telegram_id", "how_to_address"]
# Синонимы для маппинга заголовков файла
COLUMN_ALIASES = {
    "cadastral_number": ["cadastral_number", "cadastral", "кадастровый_номер", "кадастровый номер"],
    "area": ["area", "площадь"],
    "entrance": ["entrance", "подъезд", "entrance_number"],
    "floor": ["floor", "этаж"],
    "premises_type": ["premises_type", "premise_type", "тип_помещения", "тип помещения"],
    "premises_number": ["premises_number", "premise_number", "room_number", "номер_помещения", "номер помещения", "кв", "квартира"],
    "phone": ["phone", "телефон", "tel"],
    "email": ["email", "почта", "e-mail"],
    "telegram_id": ["telegram_id", "telegram", "тг"],
    "how_to_address": ["how_to_address", "как_обращаться", "обращение", "как обращаться"],
}


def _normalize_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_").replace("-", "_")


def _map_headers(headers: list[str]) -> dict[str, int]:
    """Сопоставить заголовки файла с каноническими именами колонок."""
    canonical_to_idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        norm = _normalize_header(h)
        for canonical, aliases in COLUMN_ALIASES.items():
            if norm in [ _normalize_header(a) for a in aliases ] or norm == canonical:
                if canonical not in canonical_to_idx:
                    canonical_to_idx[canonical] = i
                break
    return canonical_to_idx


def get_expected_columns() -> list[str]:
    """Список ожидаемых колонок для ответа API (LOST-02)."""
    return REQUIRED_PREMISE_COLUMNS + OPTIONAL_PREMISE_COLUMNS + CONTACT_COLUMNS


def validate_structure(detected: list[str]) -> tuple[bool, list[str], list[str]]:
    """
    Проверка структуры: обязательна хотя бы cadastral_number.
    Возвращает (ok, expected, detected).
    """
    expected = get_expected_columns()
    detected_norm = [_normalize_header(c) for c in detected]
    expected_norm = [_normalize_header(c) for c in expected]
    has_cadastral = any(
        _normalize_header(a) in detected_norm
        for aliases in [COLUMN_ALIASES["cadastral_number"]]
        for a in aliases
    )
    if not has_cadastral:
        return False, expected, detected
    return True, expected, detected


def _row_to_dict(row: list[Any], mapping: dict[str, int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, idx in mapping.items():
        if idx < len(row):
            val = row[idx]
            if hasattr(val, "strip"):
                val = val.strip() if val else ""
            elif val is not None:
                val = str(val).strip()
            else:
                val = ""
            out[key] = val or None
    return out


def _read_csv(content: bytes) -> tuple[list[str], list[list[Any]]]:
    """Прочитать CSV UTF-8 (SR-CORE01-002)."""
    text_content = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text_content), delimiter=";")
    rows = list(reader)
    if not rows:
        raise ValueError("Empty file")
    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    return headers, data_rows


def _read_xlsx(content: bytes) -> tuple[list[str], list[list[Any]]]:
    """Прочитать первый лист XLSX (SR-CORE01-003)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if not ws:
        raise ValueError("No sheet")
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Empty sheet")
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    data_rows = [[str(c).strip() if c is not None else "" for c in r] for r in rows[1:]]
    return headers, data_rows


def _read_xls(content: bytes) -> tuple[list[str], list[list[Any]]]:
    """Прочитать первый лист XLS (SR-CORE01-003)."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=content)
    sheet = wb.sheet_by_index(0)
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    data_rows = [
        [str(sheet.cell_value(r, c)).strip() if sheet.cell_value(r, c) else "" for c in range(sheet.ncols)]
        for r in range(1, sheet.nrows)
    ]
    return headers, data_rows


def parse_file(content: bytes, filename: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """
    Определить формат по расширению/содержимому, распарсить.
    Возвращает (original_headers, canonical_columns, list of row dicts).
    """
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        headers, data_rows = _read_csv(content)
    elif fn.endswith(".xlsx"):
        headers, data_rows = _read_xlsx(content)
    elif fn.endswith(".xls"):
        headers, data_rows = _read_xls(content)
    else:
        if content[:4] == b"PK\x03\x04":
            headers, data_rows = _read_xlsx(content)
        else:
            headers, data_rows = _read_csv(content)
    original_headers = [h for h in headers if (h or "").strip()]
    mapping = _map_headers(headers)
    rows = [_row_to_dict(r, mapping) for r in data_rows]
    return original_headers, list(mapping.keys()), rows


def _get_or_create_premise(
    db, cadastral_number: str, area, entrance, floor, premises_type, premises_number: str
) -> str:
    """Получить кадастровый номер помещения (существующего или созданного) (SR-CORE01-006)."""
    # Проверка существования строки: не вставлять дубликат по PK при повторном появлении кадастра в импорте.
    row = db.execute(
        text("SELECT 1 FROM premises WHERE cadastral_number = :cn"),
        {"cn": cadastral_number},
    ).fetchone()
    if row:
        return cadastral_number
    db.execute(
        text(
            "INSERT INTO premises (cadastral_number, area, entrance, floor, premises_type, premises_number) "
            "VALUES (:cn, :area, :entrance, :floor, :pt, :pn)"
        ),
        {
            "cn": cadastral_number,
            "area": area,
            "entrance": entrance,
            "floor": floor,
            "pt": premises_type,
            "pn": premises_number,
        },
    )
    db.flush()
    return cadastral_number


def _find_contact_by_indexes(db, premise_id: str, phone_idx, email_idx, telegram_id_idx) -> dict | None:
    """Найти контакт по premise_id (cadastral_number) и любому из Blind Index. Возвращает id, индексы (для коллизии) и флаги заполненности (для обогащения SR-CORE01-014)."""
    cols = "id, phone_idx, email_idx, telegram_id_idx, (COALESCE(trim(phone),'') != '') as has_phone, (COALESCE(trim(email),'') != '') as has_email, (COALESCE(trim(telegram_id),'') != '') as has_telegram_id, (COALESCE(trim(how_to_address),'') != '') as has_how"
    if phone_idx:
        r = db.execute(
            text(f"SELECT {cols} FROM contacts WHERE premise_id = :pid AND phone_idx = :pi"),
            {"pid": premise_id, "pi": phone_idx},
        ).fetchone()
        if r:
            return {"id": r[0], "phone_idx": r[1], "email_idx": r[2], "telegram_id_idx": r[3], "has_phone": r[4], "has_email": r[5], "has_telegram_id": r[6], "has_how": r[7]}
    if email_idx:
        r = db.execute(
            text(f"SELECT {cols} FROM contacts WHERE premise_id = :pid AND email_idx = :ei"),
            {"pid": premise_id, "ei": email_idx},
        ).fetchone()
        if r:
            return {"id": r[0], "phone_idx": r[1], "email_idx": r[2], "telegram_id_idx": r[3], "has_phone": r[4], "has_email": r[5], "has_telegram_id": r[6], "has_how": r[7]}
    if telegram_id_idx:
        r = db.execute(
            text(f"SELECT {cols} FROM contacts WHERE premise_id = :pid AND telegram_id_idx = :ti"),
            {"pid": premise_id, "ti": telegram_id_idx},
        ).fetchone()
        if r:
            return {"id": r[0], "phone_idx": r[1], "email_idx": r[2], "telegram_id_idx": r[3], "has_phone": r[4], "has_email": r[5], "has_telegram_id": r[6], "has_how": r[7]}
    return None


def _collision(existing: dict, row: dict, phone_idx, email_idx, telegram_id_idx) -> str | None:
    """SR-CORE01-016: тот же индекс, но в файле другой идентификатор противоречит БД (уже заполнен иным значением)."""
    if not existing:
        return None
    reasons = []
    if row.get("phone") and phone_idx and existing.get("email_idx") and email_idx and existing.get("email_idx") != email_idx:
        reasons.append("phone matches existing contact, email contradicts")
    if row.get("email") and email_idx and existing.get("phone_idx") and phone_idx and existing.get("phone_idx") != phone_idx:
        reasons.append("email matches existing contact, phone contradicts")
    if row.get("telegram_id") and telegram_id_idx:
        if existing.get("phone_idx") and phone_idx and existing.get("phone_idx") != phone_idx:
            reasons.append("telegram_id matches existing contact, phone contradicts")
        if existing.get("email_idx") and email_idx and existing.get("email_idx") != email_idx:
            reasons.append("telegram_id matches existing contact, email contradicts")
    return "; ".join(reasons) if reasons else None


def run_import(rows: list[dict[str, Any]], client_ip: str | None = None) -> dict[str, Any]:
    """
    Выполнить импорт в транзакции. Все валидные строки записываются; ошибки по строкам в отчёте.
    Возвращает { accepted, rejected, errors: [ { row, message } ] }.
    """
    accepted = 0
    rejected = 0
    errors: list[dict[str, Any]] = []
    with get_db() as db:
        try:
            for row_num, row in enumerate(rows, start=2):
                row_1based = row_num
                cadastral = (row.get("cadastral_number") or "").strip()
                if not cadastral:
                    errors.append({"row": row_1based, "message": "Missing required field: cadastral_number"})
                    rejected += 1
                    continue
                phone = (row.get("phone") or "").strip() or None
                email = (row.get("email") or "").strip() or None
                telegram_id = (row.get("telegram_id") or "").strip() or None
                how_to_address = (row.get("how_to_address") or "").strip() or None
                has_contact = phone or email or telegram_id
                premises_number_raw = (row.get("premises_number") or "").strip() or None
                premises_number = normalize_room_number(premises_number_raw) or premises_number_raw or ""
                try:
                    premise_id = _get_or_create_premise(
                        db,
                        cadastral,
                        row.get("area") or None,
                        row.get("entrance") or None,
                        row.get("floor") or None,
                        row.get("premises_type") or None,
                        premises_number,
                    )
                except Exception as e:
                    errors.append({"row": row_1based, "message": f"Premise error: {e}"})
                    rejected += 1
                    continue
                # Если контактных данных нет — помещение создано, контакт не добавляется
                if not has_contact:
                    accepted += 1
                    continue
                phone_idx = blind_index_phone(phone) if phone else None
                email_idx = blind_index_email(email) if email else None
                telegram_id_idx = blind_index_telegram_id(telegram_id) if telegram_id else None
                existing = _find_contact_by_indexes(db, premise_id, phone_idx, email_idx, telegram_id_idx)
                collision_msg = _collision(existing, row, phone_idx, email_idx, telegram_id_idx)
                if collision_msg:
                    errors.append({"row": row_1based, "message": f"Collision: {collision_msg}"})
                    rejected += 1
                    continue
                phone_enc = encrypt(phone)
                email_enc = encrypt(email)
                telegram_id_enc = encrypt(telegram_id)
                how_enc = encrypt(how_to_address)
                if existing:
                    contact_id = existing["id"]
                    updates = []
                    params = {"cid": contact_id}
                    if email_enc and not existing.get("has_email"):
                        updates.append("email = :email"); params["email"] = email_enc; params["email_idx"] = email_idx
                    if phone_enc and not existing.get("has_phone"):
                        updates.append("phone = :phone"); params["phone"] = phone_enc; params["phone_idx"] = phone_idx
                    if telegram_id_enc and not existing.get("has_telegram_id"):
                        updates.append("telegram_id = :telegram_id"); params["telegram_id"] = telegram_id_enc; params["telegram_id_idx"] = telegram_id_idx
                    if how_enc and not existing.get("has_how"):
                        updates.append("how_to_address = :how_to_address"); params["how_to_address"] = how_enc
                    if updates:
                        set_parts = updates.copy()
                        if "email_idx" in params: set_parts.append("email_idx = :email_idx")
                        if "phone_idx" in params: set_parts.append("phone_idx = :phone_idx")
                        if "telegram_id_idx" in params: set_parts.append("telegram_id_idx = :telegram_id_idx")
                        set_parts.append("updated_at = CURRENT_TIMESTAMP")
                        db.execute(text("UPDATE contacts SET " + ", ".join(set_parts) + " WHERE id = :cid"), params)
                    accepted += 1
                else:
                    db.execute(
                        text(
                            "INSERT INTO contacts (premise_id, is_owner, phone, email, telegram_id, how_to_address, "
                            "phone_idx, email_idx, telegram_id_idx, status, ip) "
                            "VALUES (:pid, true, :phone, :email, :telegram_id, :how_to_address, "
                            ":phone_idx, :email_idx, :telegram_id_idx, 'pending', :ip)"
                        ),
                        {
                            "pid": premise_id,
                            "phone": phone_enc,
                            "email": email_enc,
                            "telegram_id": telegram_id_enc,
                            "how_to_address": how_enc,
                            "phone_idx": phone_idx,
                            "email_idx": email_idx,
                            "telegram_id_idx": telegram_id_idx,
                            "ip": client_ip,
                        },
                    )
                    accepted += 1
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("Import transaction failed")
            raise
    return {"accepted": accepted, "rejected": rejected, "errors": errors}
