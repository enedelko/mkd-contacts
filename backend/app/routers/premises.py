"""
FE-03: API каскадных фильтров помещений (SR-FE03-001..005).
Подъезд → Этаж → Тип → Номер помещения; premise_id = cadastral_number.
Каскад адаптивный: пустые уровни (например, подъезд) пропускаются автоматически.
"""
from typing import Any

from fastapi import APIRouter, Query

from app.db import get_db
from app.room_normalizer import normalize_room_number
from sqlalchemy import text

router = APIRouter(prefix="/api/premises", tags=["premises"])


def _where_entrance(entrance: str | None) -> tuple[str, dict]:
    """Условие фильтрации по подъезду: если передан — фильтруем, иначе пропускаем."""
    if entrance:
        return "entrance = :e", {"e": entrance}
    return "1=1", {}


@router.get("/normalize")
def normalize_number(number: str = Query(..., description="Номер помещения для нормализации (как при импорте)")) -> dict[str, Any]:
    """SR-FE03-007, FE-04: та же функция нормализации, что и при импорте (CORE-01)."""
    return {"normalized": normalize_room_number(number)}


@router.get("/entrances")
def list_entrances(
    building_id: str | None = Query(None, description="Опционально при одном доме"),
) -> dict[str, Any]:
    """SR-FE03-001: список уникальных подъездов."""
    with get_db() as db:
        rows = db.execute(
            text("SELECT DISTINCT entrance FROM premises WHERE entrance IS NOT NULL AND trim(entrance) != '' ORDER BY entrance")
        ).fetchall()
    return {"entrances": [r[0] for r in rows]}


@router.get("/floors")
def list_floors(
    entrance: str | None = Query(None, description="Выбранный подъезд (опционально)"),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-002: список этажей, опционально по подъезду."""
    ew, ep = _where_entrance(entrance)
    with get_db() as db:
        rows = db.execute(
            text(f"SELECT DISTINCT floor FROM premises WHERE {ew} AND floor IS NOT NULL AND trim(floor) != '' ORDER BY floor"),
            ep,
        ).fetchall()
    return {"floors": [r[0] for r in rows]}


@router.get("/types")
def list_types(
    floor: str = Query(..., description="Выбранный этаж"),
    entrance: str | None = Query(None),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-003: список типов помещений по этажу, опционально по подъезду."""
    ew, ep = _where_entrance(entrance)
    with get_db() as db:
        rows = db.execute(
            text(f"SELECT DISTINCT premises_type FROM premises WHERE {ew} AND floor = :f AND premises_type IS NOT NULL AND trim(premises_type) != '' ORDER BY premises_type"),
            {**ep, "f": floor},
        ).fetchall()
    return {"types": [r[0] for r in rows]}


@router.get("/numbers")
def list_numbers(
    floor: str = Query(...),
    type: str = Query(..., alias="type", description="Тип помещения"),
    entrance: str | None = Query(None),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-004, SR-FE03-005: список номеров помещений и premise_id (cadastral_number)."""
    ew, ep = _where_entrance(entrance)
    with get_db() as db:
        rows = db.execute(
            text(
                f"SELECT premises_number, cadastral_number FROM premises "
                f"WHERE {ew} AND floor = :f AND premises_type = :pt "
                f"ORDER BY premises_number"
            ),
            {**ep, "f": floor, "pt": type},
        ).fetchall()
    return {
        "premises": [
            {"number": r[0] or "", "premise_id": r[1] or ""}
            for r in rows
        ],
    }
