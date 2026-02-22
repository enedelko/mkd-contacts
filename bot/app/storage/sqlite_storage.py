"""
Persistent FSM storage backed by SQLite (aiosqlite).
Survives container restarts via Docker volume.
TTL: stale sessions are cleaned on read.
"""
import json
import logging
import time
from typing import Any

import aiosqlite
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType

logger = logging.getLogger(__name__)


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str, ttl_seconds: int = 3600):
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._db: aiosqlite.Connection | None = None

    async def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute(
                "CREATE TABLE IF NOT EXISTS fsm_state ("
                "  key TEXT PRIMARY KEY,"
                "  state TEXT,"
                "  data TEXT DEFAULT '{}',"
                "  updated_at REAL NOT NULL"
                ")"
            )
            await self._db.execute(
                "CREATE TABLE IF NOT EXISTS broadcast_recipients ("
                "  chat_id INTEGER PRIMARY KEY"
                ")"
            )
            await self._db.commit()
        return self._db

    def _make_key(self, key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}"

    def _is_expired(self, updated_at: float) -> bool:
        return (time.time() - updated_at) > self._ttl

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        db = await self._ensure_db()
        k = self._make_key(key)
        state_str = state.state if isinstance(state, State) else state
        now = time.time()
        await db.execute(
            "INSERT INTO fsm_state (key, state, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at",
            (k, state_str, now),
        )
        await db.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        db = await self._ensure_db()
        k = self._make_key(key)
        async with db.execute("SELECT state, updated_at FROM fsm_state WHERE key = ?", (k,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        if self._is_expired(row[1]):
            await self._delete(k)
            return None
        return row[0]

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        db = await self._ensure_db()
        k = self._make_key(key)
        now = time.time()
        data_json = json.dumps(data, ensure_ascii=False)
        await db.execute(
            "INSERT INTO fsm_state (key, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (k, data_json, now),
        )
        await db.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        db = await self._ensure_db()
        k = self._make_key(key)
        async with db.execute("SELECT data, updated_at FROM fsm_state WHERE key = ?", (k,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return {}
        if self._is_expired(row[1]):
            await self._delete(k)
            return {}
        try:
            return json.loads(row[0]) if row[0] else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    async def _delete(self, k: str) -> None:
        db = await self._ensure_db()
        await db.execute("DELETE FROM fsm_state WHERE key = ?", (k,))
        await db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def cleanup_expired(self) -> int:
        db = await self._ensure_db()
        cutoff = time.time() - self._ttl
        async with db.execute("DELETE FROM fsm_state WHERE updated_at < ?", (cutoff,)) as cur:
            count = cur.rowcount
        await db.commit()
        return count or 0

    async def add_broadcast_recipient(self, chat_id: int) -> None:
        """Добавить chat_id в список получателей рассылки (при /start или первом взаимодействии)."""
        db = await self._ensure_db()
        await db.execute(
            "INSERT OR IGNORE INTO broadcast_recipients (chat_id) VALUES (?)",
            (chat_id,),
        )
        await db.commit()

    async def get_all_broadcast_chat_ids(self) -> list[int]:
        """Список всех chat_id для рассылки суперадмином."""
        db = await self._ensure_db()
        async with db.execute("SELECT chat_id FROM broadcast_recipients") as cur:
            rows = await cur.fetchall()
        return [r[0] for r in rows]
