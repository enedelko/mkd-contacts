"""Простой лимит запросов по IP и telegram_id_idx (FE-04, BOT-02: 10 записей/час)."""
import time
from collections import defaultdict

_CUTOFF = 3600  # 1 hour

# ip -> list of timestamps (last N submissions)
_submits: dict[str, list[float]] = defaultdict(list)
# telegram_id_idx -> list of timestamps (BOT-02)
_bot_submits: dict[str, list[float]] = defaultdict(list)


def _check_rate(store: dict[str, list[float]], key: str, limit: int) -> tuple[bool, int]:
    if not key:
        return True, 0
    now = time.time()
    k = key.strip() or "unknown"
    store[k] = [t for t in store[k] if now - t < _CUTOFF]
    if len(store[k]) >= limit:
        oldest = min(store[k])
        retry_after = int(oldest + _CUTOFF - now)
        return False, max(1, retry_after)
    store[k].append(now)
    return True, 0


def check_submit_rate_limit(ip: str | None, limit: int) -> tuple[bool, int]:
    """FE-04: лимит по IP."""
    return _check_rate(_submits, ip or "", limit)


def check_bot_rate_limit(telegram_id_idx: str | None, limit: int) -> tuple[bool, int]:
    """BOT-02: лимит по telegram_id_idx (blind index)."""
    return _check_rate(_bot_submits, telegram_id_idx or "", limit)
