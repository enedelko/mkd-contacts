"""
CORE-01: POST /api/admin/import/register — загрузка реестра (CSV/XLS/XLSX).
Доступ только для авторизованного администратора (SR-CORE01-001).
LOST-02: при несовпадении колонок — 400 с expected_columns, detected_columns.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.import_register import (
    get_expected_columns,
    parse_file,
    run_import,
)
from app.jwt_utils import require_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB (NFR Performance)


@router.post("/import/register")
def import_register(
    file: UploadFile = File(...),
    payload: dict = Depends(require_super_admin),
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
