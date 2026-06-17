from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bot.config import Settings
from bot.db import Database, UserRow
from bot.utils import get_next_monday_midnight, get_week_id, now_in_tz, parse_iso


@dataclass
class QuotaStatus:
    used_seconds: int
    remaining_seconds: int
    weekly_limit_seconds: int
    is_blocked: bool
    blocked_until: datetime | None
    week_id: str
    has_active_session: bool


class QuotaService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def current_week_id(self, now: datetime | None = None) -> str:
        now = now or now_in_tz(self.settings.timezone)
        return get_week_id(now, self.settings.timezone)

    async def ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        display_name: str | None,
        now: datetime | None = None,
    ) -> UserRow:
        now = now or now_in_tz(self.settings.timezone)
        week_id = self.current_week_id(now)
        user = await self.db.upsert_user(telegram_id, username, display_name, week_id)
        if user.week_id != week_id:
            await self.db.update_user_week(telegram_id, week_id)
            user = await self.db.get_user(telegram_id)
            assert user is not None
        return user

    def is_blocked(self, user: UserRow, now: datetime | None = None) -> bool:
        if not user.blocked_until:
            return False
        now = now or now_in_tz(self.settings.timezone)
        blocked_until = parse_iso(user.blocked_until)
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=now.tzinfo)
        return now < blocked_until.astimezone(now.tzinfo)

    def remaining_seconds(self, user: UserRow) -> int:
        return max(0, self.settings.weekly_limit_seconds - user.used_seconds)

    async def get_status(
        self,
        telegram_id: int,
        username: str | None,
        display_name: str | None,
        now: datetime | None = None,
    ) -> QuotaStatus:
        now = now or now_in_tz(self.settings.timezone)
        user = await self.ensure_user(telegram_id, username, display_name, now)
        active = await self.db.get_active_session_for_user(telegram_id)
        blocked_until = parse_iso(user.blocked_until) if user.blocked_until else None
        return QuotaStatus(
            used_seconds=user.used_seconds,
            remaining_seconds=self.remaining_seconds(user),
            weekly_limit_seconds=self.settings.weekly_limit_seconds,
            is_blocked=self.is_blocked(user, now),
            blocked_until=blocked_until,
            week_id=user.week_id,
            has_active_session=active is not None,
        )

    async def block_until_next_week(self, telegram_id: int, now: datetime | None = None) -> datetime:
        now = now or now_in_tz(self.settings.timezone)
        blocked_until = get_next_monday_midnight(now, self.settings.timezone)
        await self.db.set_blocked_until(telegram_id, blocked_until)
        return blocked_until

    async def reset_week_for_all(self, now: datetime | None = None) -> str:
        now = now or now_in_tz(self.settings.timezone)
        week_id = self.current_week_id(now)
        await self.db.force_stop_active_sessions("week_reset")
        await self.db.reset_all_users_for_week(week_id)
        return week_id
