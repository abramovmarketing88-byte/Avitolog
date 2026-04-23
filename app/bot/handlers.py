import asyncio
import json
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message

from app.services.openai_service import OpenAIService


logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Отправьте текст объявления одним сообщением. В ответ пришлю JSON-файл.")


@router.message(F.text, ~F.text.startswith("/"))
async def on_text(
    message: Message,
    openai_service: OpenAIService,
    assistant_id: str,
    user_message_suffix: str = "",
) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        await message.answer("Текст пустой. Напишите сообщение с содержанием.")
        return

    suffix = (user_message_suffix or "").strip()
    payload = f"{user_text}\n\n{suffix}" if suffix else user_text

    status = await message.answer("Обрабатываю…")
    try:
        result = await asyncio.to_thread(openai_service.run_assistant, assistant_id, payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Assistant error")
        await status.edit_text(f"Ошибка: {exc}")
        return

    if not result.strip():
        await status.edit_text("Ассистент вернул пустой ответ. Попробуйте переформулировать текст.")
        return

    payload = {"html_template": result.strip()}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    await status.delete()
    await message.answer_document(
        BufferedInputFile(data, filename="result.json"),
        caption="Готово: отправил JSON-файл.",
    )


@router.message(~F.text)
async def on_non_text(message: Message) -> None:
    await message.answer("Нужно текстовое сообщение.")
