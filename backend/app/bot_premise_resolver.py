"""
BOT-01: Resolve premise from free-text user input.
Loads synonym table (premise_type_aliases) from DB, normalizes input,
parses type+number, fuzzy-matches via rapidfuzz, logs unrecognized.
"""
import logging
import re
from typing import Any

from sqlalchemy import text as sa_text

from app.db import get_db
from app.room_normalizer import normalize_room_number

logger = logging.getLogger(__name__)

_aliases_cache: dict[str, tuple[str, str]] | None = None
_short_names_cache: dict[str, str] | None = None

CADASTRAL_RE = re.compile(r"\d{2}:\d{2}:\d{6,7}:\d+")
TYPE_NUMBER_RE = re.compile(r"^([а-яёa-z/.()-]+)\s*[.:,]?\s*(.+)$", re.IGNORECASE)


def _load_aliases() -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Load premise_type_aliases from DB. Returns (alias->type+short, type->short)."""
    global _aliases_cache, _short_names_cache
    if _aliases_cache is not None and _short_names_cache is not None:
        return _aliases_cache, _short_names_cache
    alias_map: dict[str, tuple[str, str]] = {}
    short_map: dict[str, str] = {}
    with get_db() as db:
        rows = db.execute(
            sa_text("SELECT premises_type, short_name, alias FROM premise_type_aliases")
        ).fetchall()
    for pt, sn, alias in rows:
        alias_map[alias.lower().strip()] = (pt, sn)
        short_map[pt] = sn
    _aliases_cache = alias_map
    _short_names_cache = short_map
    return alias_map, short_map


def reload_aliases() -> None:
    """Force reload of aliases cache (after admin edits)."""
    global _aliases_cache, _short_names_cache
    _aliases_cache = None
    _short_names_cache = None
    _load_aliases()


def _normalize_input(raw: str) -> str:
    s = raw.strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s


def _make_display(premises_type: str, premises_number: str, short_names: dict[str, str]) -> tuple[str, str]:
    display = f"{premises_type} {premises_number}"
    short = short_names.get(premises_type, premises_type)
    short_display = f"{short} {premises_number}"
    return display, short_display


def _log_unrecognized(input_text: str, telegram_id_idx: str | None) -> None:
    try:
        with get_db() as db:
            db.execute(
                sa_text("INSERT INTO bot_unrecognized (input_text, telegram_id_idx) VALUES (:t, :idx)"),
                {"t": input_text[:200], "idx": telegram_id_idx},
            )
            db.commit()
    except Exception as e:
        logger.warning("Failed to log unrecognized input: %s", e)


def resolve(raw_text: str, telegram_id_idx: str | None = None) -> list[dict[str, Any]]:
    """
    Resolve user input to a list of premise matches.
    Returns list of {premise_id, display, short_display, confidence}.
    """
    if not raw_text or len(raw_text) > 100:
        return []

    alias_map, short_names = _load_aliases()
    normalized = _normalize_input(raw_text)

    if CADASTRAL_RE.fullmatch(normalized):
        with get_db() as db:
            row = db.execute(
                sa_text("SELECT cadastral_number, premises_type, premises_number FROM premises WHERE cadastral_number = :cn"),
                {"cn": normalized},
            ).fetchone()
        if row:
            d, sd = _make_display(row[1] or "", row[2] or "", short_names)
            return [{"premise_id": row[0], "display": d, "short_display": sd, "confidence": 1.0}]
        _log_unrecognized(raw_text, telegram_id_idx)
        return []

    resolved_type: str | None = None
    number_part: str | None = None

    m = TYPE_NUMBER_RE.match(normalized)
    if m:
        type_word = m.group(1).strip().rstrip(".")
        number_raw = m.group(2).strip()
        alias_info = alias_map.get(type_word)
        if alias_info:
            resolved_type = alias_info[0]
            number_part = number_raw
        else:
            for alias_key, (pt, _sn) in alias_map.items():
                if type_word.startswith(alias_key) or alias_key.startswith(type_word):
                    resolved_type = pt
                    number_part = number_raw
                    break

    if not number_part:
        number_part = re.sub(r"[^0-9a-zа-яё]", "", normalized)
        if not number_part:
            _log_unrecognized(raw_text, telegram_id_idx)
            return []

    norm_number = normalize_room_number(number_part) or number_part

    with get_db() as db:
        if resolved_type:
            rows = db.execute(
                sa_text(
                    "SELECT cadastral_number, premises_type, premises_number FROM premises "
                    "WHERE premises_type = :pt AND premises_number = :pn"
                ),
                {"pt": resolved_type, "pn": norm_number},
            ).fetchall()
            if not rows:
                rows = db.execute(
                    sa_text(
                        "SELECT cadastral_number, premises_type, premises_number FROM premises "
                        "WHERE premises_type = :pt AND LOWER(premises_number) = LOWER(:pn)"
                    ),
                    {"pt": resolved_type, "pn": number_part},
                ).fetchall()
        else:
            rows = db.execute(
                sa_text(
                    "SELECT cadastral_number, premises_type, premises_number FROM premises "
                    "WHERE premises_number = :pn"
                ),
                {"pn": norm_number},
            ).fetchall()
            if not rows:
                rows = db.execute(
                    sa_text(
                        "SELECT cadastral_number, premises_type, premises_number FROM premises "
                        "WHERE LOWER(premises_number) = LOWER(:pn)"
                    ),
                    {"pn": number_part},
                ).fetchall()

    if rows:
        results = []
        for r in rows[:5]:
            d, sd = _make_display(r[1] or "", r[2] or "", short_names)
            conf = 1.0 if resolved_type else 0.9
            results.append({"premise_id": r[0], "display": d, "short_display": sd, "confidence": conf})
        return results

    try:
        from rapidfuzz import fuzz
        all_premises: list[tuple[str, str, str]] = []
        with get_db() as db:
            all_premises = db.execute(
                sa_text("SELECT cadastral_number, premises_type, premises_number FROM premises")
            ).fetchall()

        candidates = []
        for cn, pt, pn in all_premises:
            target = f"{pt} {pn}".lower()
            score = fuzz.ratio(normalized, target)
            if score >= 55:
                candidates.append((score, cn, pt, pn))
        candidates.sort(key=lambda x: -x[0])
        if candidates:
            results = []
            for score, cn, pt, pn in candidates[:5]:
                d, sd = _make_display(pt or "", pn or "", short_names)
                results.append({"premise_id": cn, "display": d, "short_display": sd, "confidence": round(score / 100, 2)})
            return results
    except ImportError:
        logger.warning("rapidfuzz not installed, fuzzy search disabled")

    _log_unrecognized(raw_text, telegram_id_idx)
    return []
