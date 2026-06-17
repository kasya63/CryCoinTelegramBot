from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from aiogram.types import User

from bot.config import Settings
from bot.db import Database, SessionRow
from bot.services.quota import QuotaService
from bot.utils import format_duration, now_in_tz, parse_iso, user_label


class StartResultKind(str, Enum):
    STARTED = "started"
    BLOCKED = "blocked"
    NO_QUOTA = "no_quota"
    ALREADY_ACTIVE = "already_active"


class StopResultKind(str, Enum):
    STOPPED = "stopped"
    NOT_ACTIVE = "not_active"
    NOT_OWNER = "not_owner"
    BLOCKED = "blocked"


@dataclass
class StartResult:
    kind: StartResultKind
    session: SessionRow | None = None
    remaining_seconds: int = 0


@dataclass
class StopResult:
    kind: StopResultKind
    session: SessionRow | None = None
    duration_seconds: int = 0
    remaining_seconds: int = 0
    limit_reached: bool = False


class TimerService:
    def __init__(self, db: Database, quota: QuotaService, settings: Settings) -> None:
        self.db = db
        self.quota = quota
        self.settings = settings

    async def start(self, user: User, chat_id: int, now: datetime | None = None) -> StartResult:
        now = now or now_in_tz(self.settings.timezone)
        db_user = await self.quota.ensure_user(
            user.id,
            user.username,
            user.full_name,
            now,
        )

        if self.quota.is_blocked(db_user, now):
            return StartResult(kind=StartResultKind.BLOCKED)

        if self.quota.remaining_seconds(db_user) <= 0:
            await self.quota.block_until_next_week(user.id, now)
            return StartResult(kind=StartResultKind.NO_QUOTA)

        active = await self.db.get_active_session_for_user(user.id)
        if active:
            return StartResult(kind=StartResultKind.ALREADY_ACTIVE, session=active)

        session = await self.db.create_session(user.id, chat_id, now, user.id)
        remaining = self.quota.remaining_seconds(db_user)
        return StartResult(kind=StartResultKind.STARTED, session=session, remaining_seconds=remaining)

    async def stop(
        self,
        user: User,
        now: datetime | None = None,
    ) -> StopResult:
        now = now or now_in_tz(self.settings.timezone)
        db_user = await self.quota.ensure_user(
            user.id,
            user.username,
            user.full_name,
            now,
        )

        if self.quota.is_blocked(db_user, now):
            return StopResult(kind=StopResultKind.BLOCKED)

        session = await self.db.get_active_session_for_user(user.id)
        if not session:
            return StopResult(kind=StopResultKind.NOT_ACTIVE)

        if session.started_by_user_id != user.id:
            return StopResult(kind=StopResultKind.NOT_OWNER, session=session)

        return await self._finish_session(session, now, stopped_by_user_id=user.id, status="stopped")

    async def auto_stop_session(self, session: SessionRow, now: datetime | None = None) -> StopResult:
        now = now or now_in_tz(self.settings.timezone)
        return await self._finish_session(session, now, stopped_by_user_id=None, status="auto_stopped")

    async def _finish_session(
        self,
        session: SessionRow,
        now: datetime,
        stopped_by_user_id: int | None,
        status: str,
    ) -> StopResult:
        started = parse_iso(session.started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=now.tzinfo)
        elapsed = max(0, int((now - started.astimezone(now.tzinfo)).total_seconds()))

        db_user = await self.db.get_user(session.user_id)
        assert db_user is not None

        remaining_quota = self.quota.remaining_seconds(db_user)
        billable = min(elapsed, remaining_quota)

        finished = await self.db.finish_session(
            session.id,
            now,
            billable,
            status,
            stopped_by_user_id,
        )
        if not finished:
            active = await self.db.get_session(session.id)
            if active and active.status != "active":
                return StopResult(
                    kind=StopResultKind.NOT_ACTIVE,
                    session=active,
                    duration_seconds=active.duration_seconds or 0,
                )
            return StopResult(kind=StopResultKind.NOT_ACTIVE)

        if billable > 0:
            await self.db.add_used_seconds(session.user_id, billable)

        updated_user = await self.db.get_user(session.user_id)
        assert updated_user is not None
        remaining = self.quota.remaining_seconds(updated_user)
        limit_reached = remaining <= 0

        if limit_reached:
            await self.quota.block_until_next_week(session.user_id, now)

        return StopResult(
            kind=StopResultKind.STOPPED,
            session=finished,
            duration_seconds=billable,
            remaining_seconds=remaining,
            limit_reached=limit_reached,
        )

    def format_start_message(self, user: User, remaining_seconds: int) -> str:
        return (
            f"▶️ <b>Старт</b> — {user_label(user)} начал плакать.\n"
            f"Осталось на неделю: <b>{format_duration(remaining_seconds)}</b>"
        )

    def format_stop_message(self, user: User, duration_seconds: int, remaining_seconds: int) -> str:
        return (
            f"⏹ <b>Стоп</b> — {user_label(user)} остановил таймер.\n"
            f"Сессия: <b>{format_duration(duration_seconds)}</b>\n"
            f"Осталось на неделю: <b>{format_duration(remaining_seconds)}</b>"
        )

    def format_auto_stop_message(self, user_id: int, duration_seconds: int) -> str:
        return (
            f"⛔ <b>Лимит исчерпан</b> — таймер остановлен автоматически.\n"
            f"Сессия: <b>{format_duration(duration_seconds)}</b>\n"
            f"До понедельника 00:00 (Астана) новых сессий не будет."
        )
