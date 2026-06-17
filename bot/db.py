from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite

from bot.utils import to_iso


@dataclass
class UserRow:
    telegram_id: int
    username: str | None
    display_name: str | None
    used_seconds: int
    blocked_until: str | None
    week_id: str


@dataclass
class SessionRow:
    id: int
    user_id: int
    chat_id: int
    started_at: str
    stopped_at: str | None
    duration_seconds: int | None
    status: str
    started_by_user_id: int
    stopped_by_user_id: int | None


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def init(self) -> None:
        await self.connect()
        assert self._conn is not None
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                used_seconds INTEGER NOT NULL DEFAULT 0,
                blocked_until TEXT,
                week_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                stopped_at TEXT,
                duration_seconds INTEGER,
                status TEXT NOT NULL,
                started_by_user_id INTEGER NOT NULL,
                stopped_by_user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_status
                ON sessions(user_id, status);
            CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON sessions(status);
            """
        )
        await self._conn.commit()

    async def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        assert self._conn is not None
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        assert self._conn is not None
        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return list(rows)

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        assert self._conn is not None
        async with self._conn.execute(query, params) as cursor:
            await self._conn.commit()
            return cursor.lastrowid or 0

    def _user_from_row(self, row: aiosqlite.Row) -> UserRow:
        return UserRow(
            telegram_id=row["telegram_id"],
            username=row["username"],
            display_name=row["display_name"],
            used_seconds=row["used_seconds"],
            blocked_until=row["blocked_until"],
            week_id=row["week_id"],
        )

    def _session_from_row(self, row: aiosqlite.Row) -> SessionRow:
        return SessionRow(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            started_at=row["started_at"],
            stopped_at=row["stopped_at"],
            duration_seconds=row["duration_seconds"],
            status=row["status"],
            started_by_user_id=row["started_by_user_id"],
            stopped_by_user_id=row["stopped_by_user_id"],
        )

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        display_name: str | None,
        week_id: str,
    ) -> UserRow:
        existing = await self.get_user(telegram_id)
        if existing:
            await self._execute(
                """
                UPDATE users
                SET username = ?, display_name = ?
                WHERE telegram_id = ?
                """,
                (username, display_name, telegram_id),
            )
            user = await self.get_user(telegram_id)
            assert user is not None
            return user

        await self._execute(
            """
            INSERT INTO users (telegram_id, username, display_name, used_seconds, blocked_until, week_id)
            VALUES (?, ?, ?, 0, NULL, ?)
            """,
            (telegram_id, username, display_name, week_id),
        )
        user = await self.get_user(telegram_id)
        assert user is not None
        return user

    async def get_user(self, telegram_id: int) -> UserRow | None:
        row = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return self._user_from_row(row) if row else None

    async def update_user_week(self, telegram_id: int, week_id: str) -> None:
        await self._execute(
            """
            UPDATE users
            SET week_id = ?, used_seconds = 0, blocked_until = NULL
            WHERE telegram_id = ?
            """,
            (week_id, telegram_id),
        )

    async def add_used_seconds(self, telegram_id: int, seconds: int) -> None:
        await self._execute(
            "UPDATE users SET used_seconds = used_seconds + ? WHERE telegram_id = ?",
            (seconds, telegram_id),
        )

    async def set_blocked_until(self, telegram_id: int, blocked_until: datetime | None) -> None:
        value = to_iso(blocked_until) if blocked_until else None
        await self._execute(
            "UPDATE users SET blocked_until = ? WHERE telegram_id = ?",
            (value, telegram_id),
        )

    async def reset_all_users_for_week(self, week_id: str) -> None:
        await self._execute(
            """
            UPDATE users
            SET week_id = ?, used_seconds = 0, blocked_until = NULL
            """,
            (week_id,),
        )

    async def create_session(
        self,
        user_id: int,
        chat_id: int,
        started_at: datetime,
        started_by_user_id: int,
    ) -> SessionRow:
        session_id = await self._execute(
            """
            INSERT INTO sessions (user_id, chat_id, started_at, status, started_by_user_id)
            VALUES (?, ?, ?, 'active', ?)
            """,
            (user_id, chat_id, to_iso(started_at), started_by_user_id),
        )
        session = await self.get_session(session_id)
        assert session is not None
        return session

    async def get_session(self, session_id: int) -> SessionRow | None:
        row = await self._fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return self._session_from_row(row) if row else None

    async def get_active_session_for_user(self, user_id: int) -> SessionRow | None:
        row = await self._fetchone(
            "SELECT * FROM sessions WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        return self._session_from_row(row) if row else None

    async def get_active_sessions(self) -> list[SessionRow]:
        rows = await self._fetchall("SELECT * FROM sessions WHERE status = 'active'")
        return [self._session_from_row(row) for row in rows]

    async def finish_session(
        self,
        session_id: int,
        stopped_at: datetime,
        duration_seconds: int,
        status: str,
        stopped_by_user_id: int | None,
    ) -> SessionRow | None:
        await self._execute(
            """
            UPDATE sessions
            SET stopped_at = ?, duration_seconds = ?, status = ?, stopped_by_user_id = ?
            WHERE id = ? AND status = 'active'
            """,
            (to_iso(stopped_at), duration_seconds, status, stopped_by_user_id, session_id),
        )
        return await self.get_session(session_id)

    async def force_stop_active_sessions(self, status: str = "week_reset") -> list[SessionRow]:
        active = await self.get_active_sessions()
        now = datetime.now().astimezone()
        for session in active:
            started = datetime.fromisoformat(session.started_at)
            if started.tzinfo is None:
                started = started.astimezone()
            duration = max(0, int((now - started).total_seconds()))
            await self.finish_session(session.id, now, duration, status, None)
        return active

    async def get_distinct_week_ids(self) -> list[str]:
        rows = await self._fetchall("SELECT DISTINCT week_id FROM users")
        return [row["week_id"] for row in rows]
