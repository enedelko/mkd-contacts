"""
CORE-05: Импорт участия в голосовании ОСС (CSV/XLS/XLSX).
Кадастровый номер + доля в собственности; агрегация одинаковых пар; полная перезапись таблицы.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text

from app.db import get_db
from app.import_register import COLUMN_ALIASES, _read_csv, _read_xls, _read_xlsx, _row_to_dict

logger = logging.getLogger(__name__)

VOTING_PARTICIPATION_ALIASES = {
    **COLUMN_ALIASES,
    "ownership_share": [
        "ownership_share",
        "доля_в_собственности",
        "доля в собственности",
        "доля",
    ],
}

REQUIRED_COLUMNS = ["cadastral_number", "ownership_share"]

_SHARE_FRACTION_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_SHARE_PERCENT_RE = re.compile(r"^\s*([\d.,]+)\s*%?\s*$")


def get_expected_columns_voting_participation() -> list[str]:
    return list(REQUIRED_COLUMNS)


def _map_headers_voting(headers: list[str]) -> dict[str, int]:
    canonical_to_idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        norm = (h or "").strip().lower().replace(" ", "_").replace("-", "_")
        for canonical, aliases in VOTING_PARTICIPATION_ALIASES.items():
            alias_norms = [a.strip().lower().replace(" ", "_").replace("-", "_") for a in aliases]
            if norm in alias_norms or norm == canonical:
                if canonical not in canonical_to_idx:
                    canonical_to_idx[canonical] = i
                break
    return canonical_to_idx


def parse_voting_participation_file(content: bytes, filename: str) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Распарсить файл; вернуть (original_headers, canonical_columns, rows)."""
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
    mapping = _map_headers_voting(headers)
    rows = [_row_to_dict(r, mapping) for r in data_rows]
    return original_headers, list(mapping.keys()), rows


def normalize_ownership_share(val: Any) -> Decimal | None:
    """
    Нормализовать долю в (0, 1]. Поддержка: 0.5, 0,5, 1/2, 50%, 1.
    None — невалидное значение.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        try:
            d = Decimal(str(val))
        except InvalidOperation:
            return None
    else:
        s = str(val).strip()
        if not s:
            return None
        s = s.replace(",", ".")
        frac = _SHARE_FRACTION_RE.match(s)
        if frac:
            num, den = int(frac.group(1)), int(frac.group(2))
            if den == 0:
                return None
            try:
                d = Decimal(num) / Decimal(den)
            except (InvalidOperation, ZeroDivisionError):
                return None
        elif s.endswith("%"):
            pct = _SHARE_PERCENT_RE.match(s)
            if not pct:
                return None
            try:
                d = Decimal(pct.group(1).replace(",", ".")) / Decimal(100)
            except InvalidOperation:
                return None
        else:
            try:
                d = Decimal(s)
            except InvalidOperation:
                return None

    if d <= 0 or d > 1:
        return None
    return d.quantize(Decimal("0.000001"))


def run_import_voting_participation(
    rows: list[dict[str, Any]],
    *,
    user_id: str | None = None,
    client_ip: str | None = None,
) -> dict[str, Any]:
    """
    CORE-05: импорт участия в голосовании.
    Полная перезапись oss_participation; агрегация строк с одинаковой парой кадастр+доля.
    """
    accepted = 0
    rejected = 0
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    batch_id = uuid.uuid4()

    # (premise_id, share_key) -> summed share
    aggregated: dict[tuple[str, Decimal], Decimal] = defaultdict(lambda: Decimal(0))
    # сумма всех долей по кадастру (после агрегации по парам — суммируем итоговые группы)
    cadastral_totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))

    with get_db() as db:
        try:
            for row_num, row in enumerate(rows, start=2):
                cadastral = (row.get("cadastral_number") or "").strip()
                if not cadastral:
                    errors.append({"row": row_num, "message": "Missing required field: cadastral_number"})
                    rejected += 1
                    continue

                share_raw = row.get("ownership_share")
                share = normalize_ownership_share(share_raw)
                if share is None:
                    errors.append({
                        "row": row_num,
                        "message": f"Invalid ownership share: {share_raw!r}",
                    })
                    rejected += 1
                    continue

                premise_row = db.execute(
                    text("SELECT 1 FROM premises WHERE cadastral_number = :cn"),
                    {"cn": cadastral},
                ).fetchone()
                if not premise_row:
                    errors.append({"row": row_num, "message": f"Premise not found: {cadastral}"})
                    rejected += 1
                    continue

                key = (cadastral, share)
                aggregated[key] += share
                accepted += 1

            db.execute(text("DELETE FROM oss_participation"))

            for (cadastral, share_key), total_share in aggregated.items():
                cadastral_totals[cadastral] += total_share
                db.execute(
                    text(
                        "INSERT INTO oss_participation "
                        "(premise_id, share_nominal, ownership_share, participated, import_batch_id) "
                        "VALUES (:pid, :nominal, :total, true, :batch)"
                    ),
                    {
                        "pid": cadastral,
                        "nominal": share_key,
                        "total": total_share,
                        "batch": batch_id,
                    },
                )

            for cadastral, total in cadastral_totals.items():
                if total > Decimal("1"):
                    warnings.append({
                        "cadastral_number": cadastral,
                        "message": f"Sum of shares exceeds 1.0: {total}",
                    })

            audit_payload = json.dumps({
                "accepted": accepted,
                "rejected": rejected,
                "import_batch_id": str(batch_id),
                "records_inserted": len(aggregated),
            })
            db.execute(
                text(
                    "INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, user_id, ip) "
                    "VALUES (:et, :eid, :act, NULL, :new, :uid, :ip)"
                ),
                {
                    "et": "voting_participation",
                    "eid": str(batch_id),
                    "act": "import_voting_participation",
                    "new": audit_payload,
                    "uid": user_id,
                    "ip": client_ip,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    result: dict[str, Any] = {"accepted": accepted, "rejected": rejected, "errors": errors}
    if warnings:
        result["warnings"] = warnings
    return result
