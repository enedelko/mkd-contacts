"""
CORE-01: POST /api/admin/import/register — загрузка реестра (CSV/XLS/XLSX).
ADM-06: POST /api/admin/import/contacts — загрузка только контактов.
ADM-08: GET /api/admin/import/contacts-template — шаблон XLSX по подъезду.
"""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from app.db import get_db
from app.import_register import (
    build_contacts_template_xlsx,
    get_expected_columns,
    get_expected_columns_contacts_only,
    parse_file,
    run_import,
    run_import_contacts_only,
    transliterate_entrance_for_filename,
)
from app.jwt_utils import require_admin_with_consent, require_super_admin_with_consent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    """IP клиента: за nginx — X-Forwarded-For или X-Real-IP, иначе request.client.host."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.headers.get("x-real-ip"):
        return request.headers.get("x-real-ip").strip() or None
    return request.client.host if request.client else None

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB (NFR Performance)


@router.post("/import/register")
def import_register(
    file: UploadFile = File(...),
    payload: dict = Depends(require_super_admin_with_consent),
) -> dict[str, Any]:
    """
    CORE-01: Загрузка реестра помещений и контактов (CSV, XLS, XLSX). Только суперадмин.
    multipart/form-data, поле file. Ответ: accepted, rejected, errors[].
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    try:
        original_headers, canonical_columns, rows = parse_file(content, file.filename or "")
    except ValueError as e:
        msg = str(e)
        if "Column structure mismatch" in msg or "Empty" in msg:
            raise HTTPException(
                status_code=400,
                detail=msg if "cadastral" in msg else "Column structure mismatch",
            ) from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.exception("Parse error")
        raise HTTPException(status_code=400, detail="Unsupported file format or corrupted file") from e

    if "cadastral_number" not in canonical_columns:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Column structure mismatch",
                "expected_columns": get_expected_columns(),
                "detected_columns": original_headers,
            },
        )
    # LOST-02: return body with expected/detected for client
    try:
        client_ip = None  # could be request.client.host
        report = run_import(rows, client_ip=client_ip)
    except Exception as e:
        logger.exception("Import failed")
        raise HTTPException(status_code=503, detail="Database unavailable or import failed") from e

    logger.info("Import by sub=%s: accepted=%s rejected=%s", payload.get("sub"), report["accepted"], report["rejected"])
    return report


def _audit_log(db, entity_type: str, entity_id: str, action: str, old_value: str | None, new_value: str | None, user_id: str | None, ip: str | None) -> None:
    """Запись в аудит-лог (BE-03)."""
    try:
        from sqlalchemy import text
        db.execute(
            text(
                "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user_id, ip) "
                "VALUES (:et, :eid, :act, :old, :new, :uid, :ip)"
            ),
            {"et": entity_type, "eid": entity_id, "act": action, "old": old_value, "new": new_value, "uid": user_id, "ip": ip},
        )
    except Exception as e:
        logger.warning("audit_log insert failed: %s", e)


@router.post("/import/contacts")
def import_contacts(
    file: UploadFile = File(...),
    payload: dict = Depends(require_admin_with_consent),
) -> dict[str, Any]:
    """
    ADM-06: Загрузка только контактов (CSV, XLS, XLSX). Доступна любому админу.
    Помещения не создаются; помещение с указанным кадастром должно уже быть в реестре.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    try:
        original_headers, canonical_columns, rows = parse_file(content, file.filename or "")
    except ValueError as e:
        msg = str(e)
        if "Column structure mismatch" in msg or "Empty" in msg:
            raise HTTPException(status_code=400, detail=msg if "cadastral" in msg else "Column structure mismatch") from e
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        logger.exception("Parse error")
        raise HTTPException(status_code=400, detail="Unsupported file format or corrupted file") from e

    if "cadastral_number" not in canonical_columns:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Column structure mismatch",
                "expected_columns": get_expected_columns_contacts_only(),
                "detected_columns": original_headers,
            },
        )
    has_contact_column = any(c in canonical_columns for c in ("phone", "email", "telegram_id"))
    if not has_contact_column:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "At least one contact column required: phone, email, or telegram_id",
                "expected_columns": get_expected_columns_contacts_only(),
                "detected_columns": original_headers,
            },
        )
    try:
        client_ip = None
        report = run_import_contacts_only(rows, client_ip=client_ip)
    except Exception as e:
        logger.exception("Contacts import failed")
        raise HTTPException(status_code=503, detail="Database unavailable or import failed") from e

    logger.info("Contacts import by sub=%s: accepted=%s rejected=%s", payload.get("sub"), report["accepted"], report["rejected"])
    return report


@router.get("/import/contacts-template")
def contacts_template(
    request: Request,
    entrance: str = Query(..., description="Подъезд"),
    payload: dict = Depends(require_admin_with_consent),
) -> Response:
    """
    ADM-08: Скачать XLSX-шаблон контактов по подъезду. Одна строка на контакт.
    При успешной выдаче запись в аудит-лог (при пустом подъезде — без записи).
    """
    try:
        content, row_count = build_contacts_template_xlsx(entrance)
    except Exception as e:
        logger.exception("Contacts template failed: %s", e)
        raise HTTPException(status_code=503, detail="Template generation failed") from e

    if row_count > 0:
        with get_db() as db:
            _audit_log(
                db,
                "contacts_template",
                entrance,
                "export",
                None,
                json.dumps({"row_count": row_count, "format": "xlsx"}),
                payload.get("sub"),
                _client_ip(request),
            )
            db.commit()

    # Имя файла: транслитерация кириллицы (подъезд Б → B), затем ASCII
    if row_count > 0:
        entrance_safe = transliterate_entrance_for_filename(entrance)
        filename = f"contacts_entrance_{entrance_safe}.xlsx"
    else:
        filename = "contacts_template.xlsx"
    content_disp = f'attachment; filename="{filename}"'
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disp},
    )
