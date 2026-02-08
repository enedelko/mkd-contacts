"""Простой лимит запросов по IP (FE-04: 10 записей/час)."""
import time
from collections import defaultdict

# ip -> list of timestamps (last N submissions)
_submits: dict[str, list[float]] = defaultdict(list)
_CUTOFF = 3600  # 1 hour


def check_submit_rate_limit(ip: str | None, limit: int) -> tuple[bool, int]:
    """Возвращает (allowed, retry_after_seconds). Если лимит превышен — retry_after до истечения часа."""
    if not ip:
        return True, 0
    now = time.time()
    key = ip.strip() or "unknown"
    _submits[key] = [t for t in _submits[key] if now - t < _CUTOFF]
    if len(_submits[key]) >= limit:
        oldest = min(_submits[key])
        retry_after = int(oldest + _CUTOFF - now)
        return False, max(1, retry_after)
    _submits[key].append(now)
    return True, 0
