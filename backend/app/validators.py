"""
CORE-02: Валидация форматов полей телефон, email, telegram_id (SR-CORE02-001..003).
"""
import re
from typing import Optional

# Телефон: цифры, длина 10–11, маска 7XXXXXXXXXX (SR-CORE02-001, BE-02 нормализация)
PHONE_DIGITS = re.compile(r"^\d{10,11}$")

def _phone_digits_only(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("8") and len(digits) >= 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return digits[:11]


def validate_phone(value: Optional[str]) -> tuple[bool, Optional[str]]:
    """Возвращает (ok, error_message)."""
    if not value or not str(value).strip():
        return True, None
    digits = _phone_digits_only(value.strip())
    if len(digits) < 10:
        return False, "Invalid phone format"
    if len(digits) > 11:
        return False, "Invalid phone format"
    if not digits.startswith("7"):
        return False, "Invalid phone format"
    return True, None


# Email: синтаксис (SR-CORE02-002)
EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def validate_email(value: Optional[str]) -> tuple[bool, Optional[str]]:
    if not value or not str(value).strip():
        return True, None
    s = value.strip().lower()
    if len(s) > 254:
        return False, "Invalid email format"
    if not EMAIL_RE.match(s):
        return False, "Invalid email format"
    return True, None


# Telegram ID: цифры или @username (SR-CORE02-003)
def validate_telegram_id(value: Optional[str]) -> tuple[bool, Optional[str]]:
    if not value or not str(value).strip():
        return True, None
    s = value.strip()
    if s.startswith("@"):
        if len(s) < 2 or len(s) > 32:
            return False, "Invalid telegram_id format"
        return True, None
    if not s.isdigit() or len(s) > 20:
        return False, "Invalid telegram_id format"
    return True, None
