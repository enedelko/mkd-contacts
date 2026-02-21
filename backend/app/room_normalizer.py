# CORE-01: нормализация номера помещения (SR-CORE01-018..023)
import re
from typing import Optional

# Префиксы для удаления (SR-CORE01-020a)
PREFIX_PATTERN = re.compile(
    r"^\s*(кв|пом|оф|№|подвал)(\s*[.:]\s*|\s+)?",
    re.IGNORECASE,
)

# Кириллица -> латиница (SR-CORE01-021): только постфиксы А/Б и путаница В/B
CYRILLIC_TO_LATIN = str.maketrans({"а": "a", "б": "b", "в": "b"})

# Римские I-XXX -> арабские (SR-CORE01-022)
ROMAN_TO_ARABIC = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9,
    "x": 10, "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17,
    "xviii": 18, "xix": 19, "xx": 20, "xxi": 21, "xxii": 22, "xxiii": 23, "xxiv": 24,
    "xxv": 25, "xxvi": 26, "xxvii": 27, "xxviii": 28, "xxix": 29, "xxx": 30,
}


def _extract_first_match(text: str, pattern: re.Pattern) -> Optional[str]:
    """Первое подходящее вхождение (SR-CORE01-018)."""
    if not text or not isinstance(text, str):
        return None
    m = pattern.search(text.strip())
    return m.group(1).strip() if m else None


def _roman_to_arabic(s: str) -> str:
    """Римские I-XXX в арабские (SR-CORE01-022)."""
    key = s.lower().strip()
    return str(ROMAN_TO_ARABIC.get(key, s))


def normalize_room_number(raw: Optional[str]) -> str:
    """
    Нормализованный room_id из строки номера помещения (SR-CORE01-018..023).
    Паттерны: арабские цифры; цифры с литерами (5б, 5-Б, А-23); римские I-XXX.
    Возвращает: нижний регистр, без пробелов, префиксы убраны, кириллица->латиница,
    римские->арабские.
    """
    if not raw or not str(raw).strip():
        return ""
    s = str(raw).strip()
    # Удалить префиксы (SR-CORE01-020a)
    s = PREFIX_PATTERN.sub("", s)
    # Первое вхождение: либо римские (I-XXX), либо арабские с литерой (SR-CORE01-019)
    # Цифры и буква могут быть через пробел/дефис (05 Б, 5-Б) — захватываем в одну группу
    roman_pattern = re.compile(r"\b([IVX]+)\b", re.IGNORECASE)
    arabic_literal_pattern = re.compile(
        r"\b(\d+(?:[\s\-]*[a-zA-Zа-яА-ЯёЁ])?|[a-zA-Zа-яА-ЯёЁ]?\d+)\b", re.IGNORECASE
    )
    first_roman = _extract_first_match(s, roman_pattern)
    if first_roman and first_roman.lower() in ROMAN_TO_ARABIC:
        normalized = _roman_to_arabic(first_roman)
    else:
        first = _extract_first_match(s, arabic_literal_pattern)
        normalized = first or ""
    # Нижний регистр, без пробелов (SR-CORE01-020)
    normalized = normalized.lower().replace(" ", "").replace("-", "")
    # Кириллица -> латиница (SR-CORE01-021)
    normalized = normalized.translate(CYRILLIC_TO_LATIN)
    return normalized
