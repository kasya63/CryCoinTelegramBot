import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{35,}$")
_PLACEHOLDER_TOKENS = {
    "your_token_from_botfather",
    "your_token_here",
    "paste_token_here",
}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    timezone: str
    weekly_limit_seconds: int
    db_path: str
    tick_interval_seconds: int


def load_settings() -> Settings:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        raise ValueError(
            "BOT_TOKEN не задан. Откройте .env и вставьте токен от @BotFather "
            "(команда /newbot → скопируйте строку вида 7123456789:AAH...)."
        )
    if token in _PLACEHOLDER_TOKENS or not _TOKEN_PATTERN.match(token):
        raise ValueError(
            "BOT_TOKEN в .env неверный. Замените заглушку на реальный токен от @BotFather: "
            "откройте https://t.me/BotFather → /newbot (или /token для существующего бота) "
            "и вставьте токен в файл .env как BOT_TOKEN=7123456789:AAH..."
        )

    return Settings(
        bot_token=token,
        timezone=os.getenv("TIMEZONE", "Asia/Almaty"),
        weekly_limit_seconds=int(os.getenv("WEEKLY_LIMIT_SECONDS", "14400")),
        db_path=os.getenv("DB_PATH", "crycoin.db"),
        tick_interval_seconds=int(os.getenv("TICK_INTERVAL_SECONDS", "30")),
    )
