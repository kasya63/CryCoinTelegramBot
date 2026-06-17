from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from bot.config import Settings
from bot.db import Database
from bot.services.quota import QuotaService
from bot.services.timer import StopResultKind, TimerService
from bot.utils import get_week_id, now_in_tz, parse_iso

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, bot: Bot, db: Database, settings: Settings) -> None:
        self.bot = bot
        self.db = db
        self.settings = settings
        self.quota = QuotaService(db, settings)
        self.timer = TimerService(db, self.quota, settings)
        self._task: asyncio.Task | None = None
        self._last_week_id: str | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception:
                logger.exception("Scheduler tick failed")
            await asyncio.sleep(self.settings.tick_interval_seconds)

    async def _tick(self) -> None:
        now = now_in_tz(self.settings.timezone)
        week_id = get_week_id(now, self.settings.timezone)

        if self._last_week_id is None:
            self._last_week_id = week_id
        elif week_id != self._last_week_id:
            await self._handle_week_reset(now, week_id)
            self._last_week_id = week_id
            return

        active_sessions = await self.db.get_active_sessions()
        for session in active_sessions:
            await self._check_session_limit(session, now)

    async def _handle_week_reset(self, now: datetime, week_id: str) -> None:
        logger.info("Week reset to %s", week_id)
        stopped = await self.db.force_stop_active_sessions("week_reset")
        await self.db.reset_all_users_for_week(week_id)

        for session in stopped:
            try:
                await self.bot.send_message(
                    session.chat_id,
                    "🔄 <b>Новая неделя</b> — лимит CryCoin обновлён до 4 часов. Активные сессии остановлены.",
                )
            except Exception:
                logger.exception("Failed to notify chat %s about week reset", session.chat_id)

    async def _check_session_limit(self, session, now: datetime) -> None:
        user = await self.db.get_user(session.user_id)
        if not user:
            return

        started = parse_iso(session.started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=now.tzinfo)
        elapsed = max(0, int((now - started.astimezone(now.tzinfo)).total_seconds()))
        remaining = self.quota.remaining_seconds(user)

        if elapsed < remaining:
            return

        result = await self.timer.auto_stop_session(session, now)
        if result.kind != StopResultKind.STOPPED:
            return

        try:
            await self.bot.send_message(
                session.chat_id,
                self.timer.format_auto_stop_message(session.user_id, result.duration_seconds),
            )
        except Exception:
            logger.exception("Failed to send auto-stop message to chat %s", session.chat_id)
