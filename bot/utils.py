from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import User


def format_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    if minutes > 0:
        return f"{minutes}м"
    return f"{seconds}с"


def user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    name = user.full_name.strip()
    return name or f"id:{user.id}"


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def get_tz(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def now_in_tz(timezone_name: str) -> datetime:
    return datetime.now(get_tz(timezone_name))


def get_week_id(dt: datetime, timezone_name: str) -> str:
    local = dt.astimezone(get_tz(timezone_name))
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def get_week_start(dt: datetime, timezone_name: str) -> datetime:
    local = dt.astimezone(get_tz(timezone_name))
    monday = local.date() - timedelta(days=local.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=get_tz(timezone_name))


def get_next_monday_midnight(dt: datetime, timezone_name: str) -> datetime:
    local = dt.astimezone(get_tz(timezone_name))
    days_until_monday = (7 - local.weekday()) % 7
    if days_until_monday == 0 and local.hour == 0 and local.minute == 0 and local.second == 0:
        return local
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday_date = local.date() + timedelta(days=days_until_monday)
    return datetime(
        next_monday_date.year,
        next_monday_date.month,
        next_monday_date.day,
        tzinfo=get_tz(timezone_name),
    )
