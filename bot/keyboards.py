from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Старт", callback_data="cry_start"),
                InlineKeyboardButton(text="⏹ Стоп", callback_data="cry_stop"),
            ],
            [
                InlineKeyboardButton(text="📊 Статус", callback_data="cry_status"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="cry_help"),
            ],
        ]
    )
