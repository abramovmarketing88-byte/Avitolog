import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.services.openai_service import OpenAIService


logger = logging.getLogger(__name__)
router = Router()

_TELEGRAM_CHUNK = 4000


def _split_reply(text: str, max_len: int = _TELEGRAM_CHUNK) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Отправьте текст объявления одним сообщением.")


@router.message(F.text, ~F.text.startswith("/"))
async def on_text(
    message: Message,
    openai_service: OpenAIService,
    assistant_id: str,
) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        await message.answer("Текст пустой. Напишите сообщение с содержанием.")
        return

    status = await message.answer("Обрабатываю…")
    try:
        result = await asyncio.to_thread(openai_service.run_assistant, assistant_id, user_text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Assistant error")
        await status.edit_text(f"Ошибка: {exc}")
        return

    if not result.strip():
        await status.edit_text("Ассистент вернул пустой ответ. Попробуйте переформулировать текст.")
        return

    await status.delete()
    for chunk in _split_reply(result):
        await message.answer(chunk)


@router.message(~F.text)
async def on_non_text(message: Message) -> None:
    await message.answer("Нужно текстовое сообщение.")
