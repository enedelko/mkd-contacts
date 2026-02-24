"""
FE-03: API каскадных фильтров помещений (SR-FE03-001..005).
Подъезд → Этаж → Тип → Номер помещения; premise_id = cadastral_number.
Каскад адаптивный: пустые уровни (например, подъезд) пропускаются автоматически.
"""
import re
from typing import Any

from fastapi import APIRouter, Query

from app.db import get_db
from app.room_normalizer import normalize_room_number
from sqlalchemy import text

router = APIRouter(prefix="/api/premises", tags=["premises"])


def _floor_sort_key(val: str) -> tuple[int, str]:
    """Ключ сортировки этажей: числовой порядок с fallback на строку."""
    try:
        return (int(val), "")
    except (ValueError, TypeError):
        return (999999, val or "")


def _premise_sort_key(number: str) -> tuple[int, str]:
    """Ключ сортировки помещений через normalize_room_number: числовая часть + суффикс."""
    normalized = normalize_room_number(number)
    if not normalized:
        return (999999, number or "")
    m = re.match(r"^(\d+)(.*)", normalized)
    if m:
        return (int(m.group(1)), m.group(2))
    return (999999, normalized)


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
            text(f"SELECT DISTINCT floor FROM premises WHERE {ew} AND floor IS NOT NULL AND trim(floor) != ''"),
            ep,
        ).fetchall()
    floors = sorted([r[0] for r in rows], key=_floor_sort_key)
    return {"floors": floors}


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


@router.get("/chessboard")
def chessboard(
    entrance: str = Query(..., description="Подъезд"),
) -> dict[str, Any]:
    """
    FE-06 / SR-FE06-014..015: данные для шахматки помещений выбранного подъезда.
    Публичный (без авторизации). Возвращает этажи (от макс. к мин.) с помещениями,
    флагами контактов и состоянием ОСС. ПДн не раскрываются.
    """
    with get_db() as db:
        # Все помещения подъезда с агрегатами по контактам и голосованию
        rows = db.execute(
            text("""
                SELECT
                    p.cadastral_number,
                    p.premises_type,
                    p.premises_number,
                    p.floor,
                    p.area,
                    -- кол-во активных собственников (pending + validated; только они голосуют)
                    COUNT(DISTINCT c.id) FILTER (WHERE c.status IN ('pending', 'validated') AND c.is_owner = true)  AS cnt_active,
                    -- кол-во валидированных (на будущее)
                    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'validated')                AS cnt_validated,
                    -- кол-во собственников с barrier_vote = 'for'
                    COUNT(DISTINCT c.id) FILTER (
                        WHERE c.status IN ('pending', 'validated') AND c.is_owner = true AND o.barrier_vote = 'for'
                    )                                                                          AS cnt_vote_for,
                    -- есть ли хотя бы один собственник, зарегистрированный в Электронном доме
                    BOOL_OR(c.registered_in_ed = 'yes')
                        FILTER (WHERE c.status IN ('pending', 'validated'))                    AS has_registered_ed,
                    -- есть ли telegram_id или phone среди активных
                    BOOL_OR(
                        (c.telegram_id IS NOT NULL AND c.telegram_id != '')
                        OR (c.phone IS NOT NULL AND c.phone != '')
                    ) FILTER (WHERE c.status IN ('pending', 'validated'))                      AS has_tg_or_phone,
                    -- есть ли email среди активных
                    BOOL_OR(
                        c.email IS NOT NULL AND c.email != ''
                    ) FILTER (WHERE c.status IN ('pending', 'validated'))                      AS has_email
                FROM premises p
                LEFT JOIN contacts c ON c.premise_id = p.cadastral_number
                LEFT JOIN oss_voting o ON o.contact_id = c.id
                WHERE p.entrance = :entrance
                  AND p.floor IS NOT NULL AND TRIM(p.floor) != ''
                GROUP BY p.cadastral_number, p.premises_type, p.premises_number, p.floor, p.area
            """),
            {"entrance": entrance},
        ).fetchall()

        # Площадь «ЗА» для подъезда (формула CORE-04)
        total_area_row = db.execute(
            text("SELECT COALESCE(SUM(COALESCE(area, 0)), 0) FROM premises WHERE entrance = :entrance"),
            {"entrance": entrance},
        ).fetchone()
        total_area = float(total_area_row[0] or 0)

        area_for_row = db.execute(
            text("""
                SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p
                WHERE p.entrance = :entrance
                AND EXISTS (
                    SELECT 1 FROM contacts c
                    JOIN oss_voting o ON o.contact_id = c.id
                    WHERE c.premise_id = p.cadastral_number AND c.is_owner = true AND o.barrier_vote = 'for'
                )
            """),
            {"entrance": entrance},
        ).fetchone()
        area_voted_for = float(area_for_row[0] or 0)

        # SR-FE06-017: площадь помещений подъезда с контактами в ЭД (pending/validated)
        area_ed_row = db.execute(
            text("""
                SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p
                WHERE p.entrance = :entrance
                AND EXISTS (
                    SELECT 1 FROM contacts c
                    WHERE c.premise_id = p.cadastral_number
                      AND c.registered_in_ed = 'yes'
                      AND c.status IN ('pending', 'validated')
                )
            """),
            {"entrance": entrance},
        ).fetchone()
        area_registered_ed = float(area_ed_row[0] or 0)

    # Группируем по этажам
    floors_map: dict[str, list] = {}
    for r in rows:
        cn, pt, pn, fl, area, cnt_active, cnt_validated, cnt_vote_for, has_reg_ed, has_tg, has_email = r
        # contact_state — раскраска по позиции ОСС (vote_for/full только по собственникам):
        #   full        — все активные собственники голосуют «ЗА»
        #   vote_for    — хотя бы один собственник голосует «ЗА» (но не все)
        #   registered  — хотя бы один собственник зарегистрирован в Электронном доме
        #   none        — нет информации
        if cnt_active > 0 and cnt_vote_for > 0 and cnt_vote_for >= cnt_active:
            state = "full"
        elif cnt_vote_for and cnt_vote_for > 0:
            state = "vote_for"
        elif bool(has_reg_ed):
            state = "registered"
        else:
            state = "none"

        has_tg_or_phone = bool(has_tg)
        has_email_only = bool(has_email) and not has_tg_or_phone

        item = {
            "premise_id": cn,
            "premises_type": pt or "",
            "premises_number": pn or "",
            "contact_state": state,
            "has_telegram_or_phone": has_tg_or_phone,
            "has_email_only": has_email_only,
        }
        floors_map.setdefault(fl, []).append(item)

    # Сортировка: этажи от макс. к мин., помещения по типу/номеру
    sorted_floors = sorted(floors_map.keys(), key=_floor_sort_key, reverse=True)
    floors_out = []
    for fl in sorted_floors:
        premises = floors_map[fl]
        premises.sort(key=lambda p: (p["premises_type"], _premise_sort_key(p["premises_number"])))
        floors_out.append({"floor": fl, "premises": premises})

    ratio = (area_voted_for / total_area) if total_area > 0 else 0.0
    entrance_ed_ratio = (area_registered_ed / total_area) if total_area > 0 else 0.0

    return {
        "entrance": entrance,
        "entrance_area_voted_for": round(area_voted_for, 2),
        "entrance_total_area": round(total_area, 2),
        "entrance_ratio": round(ratio, 4),
        "entrance_area_registered_ed": round(area_registered_ed, 2),
        "entrance_ed_ratio": round(entrance_ed_ratio, 4),
        "floors": floors_out,
    }


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
                f"WHERE {ew} AND floor = :f AND premises_type = :pt"
            ),
            {**ep, "f": floor, "pt": type},
        ).fetchall()
    items = [{"number": r[0] or "", "premise_id": r[1] or ""} for r in rows]
    items.sort(key=lambda p: _premise_sort_key(p["number"]))
    return {"premises": items}
