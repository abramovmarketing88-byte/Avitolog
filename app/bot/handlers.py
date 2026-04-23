import asyncio
import csv
import io
import json
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message

from app.services.openai_service import OpenAIService
from app.services.spintax_service import generate_unique_variants


logger = logging.getLogger(__name__)
router = Router()
_pending_templates: dict[int, str] = {}
_MAX_ADS_COUNT = 1000


def _extract_html_template(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(payload, dict):
        value = payload.get("html_template")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return text


def _build_csv_bytes(rows: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    # Use comma + full quoting so Excel keeps HTML in one cell.
    writer = csv.writer(
        buffer,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_ALL,
        lineterminator="\n",
    )
    writer.writerow(["description"])
    for row in rows:
        writer.writerow([row])
    return buffer.getvalue().encode("utf-8-sig")

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is not None:
        _pending_templates.pop(user_id, None)
    await message.answer(
        "Отправьте текст объявления одним сообщением.\n"
        "Сначала пришлю result.json, затем спрошу, сколько объявлений собрать в CSV."
    )


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
    user_id = message.from_user.id if message.from_user else None
    if user_id is not None and user_id in _pending_templates and user_text.isdigit():
        count = int(user_text)
        if count < 1 or count > _MAX_ADS_COUNT:
            await message.answer(f"Введите число от 1 до {_MAX_ADS_COUNT}.")
            return
        template = _pending_templates[user_id]
        status = await message.answer("Собираю CSV через спинтакс...")
        rows = await asyncio.to_thread(generate_unique_variants, template, count)
        data = _build_csv_bytes(rows)
        await status.delete()
        await message.answer_document(
            BufferedInputFile(data, filename=f"ads_{count}.csv"),
            caption=f"Готово: {len(rows)} объявлений в CSV.",
        )
        _pending_templates.pop(user_id, None)
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

    template = _extract_html_template(result)
    if not template:
        await status.edit_text("Не удалось получить html_template из ответа ассистента.")
        return
    payload = {"html_template": template}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    await status.delete()
    await message.answer_document(
        BufferedInputFile(data, filename="result.json"),
        caption="Готово: отправил JSON-файл.",
    )
    if user_id is not None:
        _pending_templates[user_id] = template
    await message.answer(f"Сколько объявлений сгенерировать в CSV? Введите число от 1 до {_MAX_ADS_COUNT}.")


@router.message(~F.text)
async def on_non_text(message: Message) -> None:
    await message.answer("Нужно текстовое сообщение.")
