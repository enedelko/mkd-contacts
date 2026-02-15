"""
Публичный API для страницы Политики конфиденциальности.
Раздел 9: перечень администраторов (ФИО и помещение) без чувствительных данных.
"""
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_db

router = APIRouter(prefix="/api/policy", tags=["policy"])


@router.get("/admins")
def list_admins_for_policy() -> list[dict[str, Any]]:
    """Список админов для раздела 9 Политики: только full_name и premises (без auth)."""
    with get_db() as db:
        rows = db.execute(
            text("SELECT full_name, premises FROM admins ORDER BY created_at")
        ).fetchall()
    return [
        {
            "full_name": r[0] or "—",
            "premises": r[1] or "—",
        }
        for r in rows
    ]
