from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Settings
from bot.db import Database
from bot.keyboards import main_keyboard
from bot.services.quota import QuotaService
from bot.utils import format_duration

router = Router()


async def _is_blocked(message: Message, db: Database, settings: Settings) -> bool:
    if not message.from_user:
        return False
    quota = QuotaService(db, settings)
    user = await quota.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    return quota.is_blocked(user)


@router.message(Command("start"))
async def cmd_start(message: Message, db: Database, settings: Settings) -> None:
    if not message.from_user:
        return
    if await _is_blocked(message, db, settings):
        return

    await message.answer(
        "😢 <b>CryCoin</b>\n\n"
        "У каждого 4 часа «плача» в неделю. Нажми <b>Старт</b>, когда начнёшь, "
        "и <b>Стоп</b>, когда закончишь.\n\n"
        "Лимит сбрасывается в понедельник 00:00 по Астане.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("status"))
async def cmd_status(message: Message, db: Database, settings: Settings) -> None:
    if not message.from_user:
        return
    if await _is_blocked(message, db, settings):
        return

    quota = QuotaService(db, settings)
    status = await quota.get_status(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )

    lines = [
        "📊 <b>Статус CryCoin</b>",
        f"Осталось: <b>{format_duration(status.remaining_seconds)}</b> "
        f"из <b>{format_duration(status.weekly_limit_seconds)}</b>",
        f"Использовано: <b>{format_duration(status.used_seconds)}</b>",
    ]
    if status.has_active_session:
        lines.append("⏱ Сейчас идёт активная сессия.")
    if status.is_blocked:
        lines.append("⛔ Лимит на эту неделю исчерпан. Ждите понедельник 00:00 (Астана).")

    await message.answer("\n".join(lines), reply_markup=main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message, db: Database, settings: Settings) -> None:
    if not message.from_user:
        return
    if await _is_blocked(message, db, settings):
        return

    await message.answer(
        "ℹ️ <b>Правила CryCoin</b>\n\n"
        "• Каждую неделю — <b>4 часа</b> личного времени.\n"
        "• <b>Старт</b> — запускает таймер для того, кто нажал.\n"
        "• <b>Стоп</b> — останавливает только свою сессию.\n"
        "• Одновременно может быть только одна активная сессия на человека.\n"
        "• Если лимит кончился — бот сам остановит таймер и замолчит до понедельника 00:00 (Астана).\n"
        "• Неиспользованное время не переносится на следующую неделю.",
        reply_markup=main_keyboard(),
    )
