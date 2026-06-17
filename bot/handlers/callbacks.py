from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import Settings
from bot.db import Database
from bot.keyboards import main_keyboard
from bot.services.quota import QuotaService
from bot.services.timer import StartResultKind, StopResultKind, TimerService

router = Router()


async def _is_blocked_callback(callback: CallbackQuery, db: Database, settings: Settings) -> bool:
    if not callback.from_user:
        return False
    quota = QuotaService(db, settings)
    user = await quota.ensure_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
    )
    return quota.is_blocked(user)


@router.callback_query(F.data == "cry_start")
async def on_start(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if not callback.from_user or not callback.message:
        return

    if await _is_blocked_callback(callback, db, settings):
        await callback.answer()
        return

    timer = TimerService(db, QuotaService(db, settings), settings)
    result = await timer.start(callback.from_user, callback.message.chat.id)

    if result.kind == StartResultKind.BLOCKED:
        await callback.answer()
        return

    if result.kind == StartResultKind.NO_QUOTA:
        await callback.answer("Лимит на эту неделю исчерпан.", show_alert=True)
        return

    if result.kind == StartResultKind.ALREADY_ACTIVE:
        await callback.answer("У вас уже идёт активная сессия.", show_alert=True)
        return

    await callback.answer("Таймер запущен!")
    await callback.message.answer(
        timer.format_start_message(callback.from_user, result.remaining_seconds),
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data == "cry_stop")
async def on_stop(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if not callback.from_user or not callback.message:
        return

    if await _is_blocked_callback(callback, db, settings):
        await callback.answer()
        return

    timer = TimerService(db, QuotaService(db, settings), settings)
    result = await timer.stop(callback.from_user)

    if result.kind == StopResultKind.BLOCKED:
        await callback.answer()
        return

    if result.kind == StopResultKind.NOT_ACTIVE:
        await callback.answer("Нет активной сессии.", show_alert=True)
        return

    if result.kind == StopResultKind.NOT_OWNER:
        await callback.answer("Остановить может только тот, кто нажал Старт.", show_alert=True)
        return

    await callback.answer("Таймер остановлен.")
    text = timer.format_stop_message(
        callback.from_user,
        result.duration_seconds,
        result.remaining_seconds,
    )
    if result.limit_reached:
        text += "\n\n⛔ Лимит на эту неделю исчерпан. До понедельника 00:00 (Астана)."

    await callback.message.answer(text, reply_markup=main_keyboard())
