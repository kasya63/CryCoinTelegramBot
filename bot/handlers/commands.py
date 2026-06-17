from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Settings
from bot.db import Database
from bot.keyboards import main_keyboard
from bot.services.quota import QuotaService
from bot.texts import HELP_TEXT, format_status_message

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

    await message.answer(format_status_message(status), reply_markup=main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message, db: Database, settings: Settings) -> None:
    if not message.from_user:
        return
    if await _is_blocked(message, db, settings):
        return

    await message.answer(HELP_TEXT, reply_markup=main_keyboard())
