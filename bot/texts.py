from bot.services.quota import QuotaStatus
from bot.utils import format_duration

HELP_TEXT = (
    "ℹ️ <b>Правила CryCoin</b>\n\n"
    "• Каждую неделю — <b>4 часа</b> личного времени.\n"
    "• <b>Старт</b> — запускает таймер для того, кто нажал.\n"
    "• <b>Стоп</b> — останавливает только свою сессию.\n"
    "• Одновременно может быть только одна активная сессия на человека.\n"
    "• Если лимит кончился — бот сам остановит таймер и замолчит до понедельника 00:00 (Астана).\n"
    "• Неиспользованное время не переносится на следующую неделю."
)


def format_status_message(status: QuotaStatus) -> str:
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
    return "\n".join(lines)
