"""
FE-03: API каскадных фильтров помещений (SR-FE03-001..005).
Подъезд → Этаж → Тип → Номер помещения; premise_id = cadastral_number.
"""
from typing import Any

from fastapi import APIRouter, Query

from app.db import get_db
from app.room_normalizer import normalize_room_number
from sqlalchemy import text

router = APIRouter(prefix="/api/premises", tags=["premises"])


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
    entrance: str = Query(..., description="Выбранный подъезд"),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-002: список этажей по подъезду."""
    with get_db() as db:
        rows = db.execute(
            text("SELECT DISTINCT floor FROM premises WHERE entrance = :e AND floor IS NOT NULL AND trim(floor) != '' ORDER BY floor"),
            {"e": entrance},
        ).fetchall()
    return {"floors": [r[0] for r in rows]}


@router.get("/types")
def list_types(
    entrance: str = Query(...),
    floor: str = Query(..., description="Выбранный этаж"),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-003: список типов помещений по подъезду и этажу."""
    with get_db() as db:
        rows = db.execute(
            text("SELECT DISTINCT premises_type FROM premises WHERE entrance = :e AND floor = :f AND premises_type IS NOT NULL AND trim(premises_type) != '' ORDER BY premises_type"),
            {"e": entrance, "f": floor},
        ).fetchall()
    return {"types": [r[0] for r in rows]}


@router.get("/numbers")
def list_numbers(
    entrance: str = Query(...),
    floor: str = Query(...),
    type: str = Query(..., alias="type", description="Тип помещения"),
    building_id: str | None = Query(None),
) -> dict[str, Any]:
    """SR-FE03-004, SR-FE03-005: список номеров помещений и premise_id (cadastral_number)."""
    with get_db() as db:
        rows = db.execute(
            text(
                "SELECT premises_number, cadastral_number FROM premises "
                "WHERE entrance = :e AND floor = :f AND premises_type = :pt "
                "ORDER BY premises_number"
            ),
            {"e": entrance, "f": floor, "pt": type},
        ).fetchall()
    return {
        "premises": [
            {"number": r[0] or "", "premise_id": r[1] or ""}
            for r in rows
        ],
    }
