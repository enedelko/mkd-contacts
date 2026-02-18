"""
CORE-04: GET /api/buildings/{building_id}/quorum — базовый расчёт кворума.
Публичный доступ. building_id = префикс кадастра или "default" (все помещения).
"""
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_db

router = APIRouter(tags=["quorum"])

QUORUM_THRESHOLD = 2 / 3  # 0.667


@router.get("/api/buildings/{building_id}/quorum")
def get_quorum(building_id: str) -> dict[str, Any]:
    """
    SR-CORE04-001..005: общая площадь, площадь «ЗА», доля, порог 2/3, кворум достигнут/нет.
    building_id = префикс кадастрового номера (напр. 77:01:0001001) или "default" — все помещения.
    """
    use_prefix = building_id != "default"
    params: dict[str, Any] = {}
    where = "1=1"
    if use_prefix:
        where = "starts_with(cadastral_number, :bid)"
        params["bid"] = building_id

    with get_db() as db:
        total_row = db.execute(
            text(
                f"SELECT COALESCE(SUM(COALESCE(area, 0)), 0) FROM premises WHERE {where}"
            ),
            params,
        ).fetchone()
        total_area = float(total_row[0] or 0)

        if use_prefix:
            area_for_row = db.execute(
                text("""
                    SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p
                    WHERE starts_with(p.cadastral_number, :bid)
                    AND EXISTS (
                        SELECT 1 FROM contacts c
                        JOIN oss_voting o ON o.contact_id = c.id
                        WHERE c.premise_id = p.cadastral_number AND o.barrier_vote = 'for'
                    )
                """),
                {"bid": building_id},
            ).fetchone()
        else:
            area_for_row = db.execute(
                text("""
                    SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p
                    WHERE EXISTS (
                        SELECT 1 FROM contacts c
                        JOIN oss_voting o ON o.contact_id = c.id
                        WHERE c.premise_id = p.cadastral_number AND o.barrier_vote = 'for'
                    )
                """)
            ).fetchone()
        area_voted_for = float(area_for_row[0] or 0)

        # SR-CORE04-007: площадь помещений с хотя бы одним контактом в ЭД (pending/validated)
        ed_exists = """
            EXISTS (
                SELECT 1 FROM contacts c
                WHERE c.premise_id = p.cadastral_number
                  AND c.registered_in_ed = 'yes'
                  AND c.status IN ('pending', 'validated')
            )
        """
        if use_prefix:
            area_ed_row = db.execute(
                text(f"""
                    SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p
                    WHERE starts_with(p.cadastral_number, :bid) AND {ed_exists}
                """),
                {"bid": building_id},
            ).fetchone()
        else:
            area_ed_row = db.execute(
                text(f"SELECT COALESCE(SUM(COALESCE(p.area, 0)), 0) FROM premises p WHERE {ed_exists}")
            ).fetchone()
        area_registered_ed = float(area_ed_row[0] or 0)

    ratio = (area_voted_for / total_area) if total_area > 0 else 0.0
    quorum_reached = ratio >= QUORUM_THRESHOLD
    ed_ratio = (area_registered_ed / total_area) if total_area > 0 else 0.0

    return {
        "total_area": round(total_area, 2),
        "area_voted_for": round(area_voted_for, 2),
        "ratio": round(ratio, 4),
        "quorum_threshold": round(QUORUM_THRESHOLD, 4),
        "quorum_reached": quorum_reached,
        "area_registered_ed": round(area_registered_ed, 2),
        "ed_ratio": round(ed_ratio, 4),
    }
