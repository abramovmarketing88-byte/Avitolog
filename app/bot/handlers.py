import asyncio
import logging
import os
import re
import tempfile
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.agents.jtbd_agent import JTBDAgent
from app.services.excel_service import export_ads_to_excel
from app.services.geo_service import generate_geo
from app.services.orchestrator import AdsOrchestrator, GenerationConfig
from app.bot.states import AdGenerationStates


logger = logging.getLogger(__name__)
router = Router()

ALLOWED_GEO = {"city", "metro", "district", "address"}
GEO_ALIASES = {
    "city": "city",
    "город": "city",
    "города": "city",
    "городу": "city",
    "по городу": "city",
    "metro": "metro",
    "метро": "metro",
    "district": "district",
    "район": "district",
    "районы": "district",
    "address": "address",
    "адрес": "address",
    "адреса": "address",
}
AUTO_CITIES = (
    "Москва,Санкт-Петербург,Новосибирск,Екатеринбург,Казань,Нижний Новгород,Челябинск,Самара,"
    "Омск,Ростов-на-Дону,Уфа,Красноярск,Пермь,Воронеж,Волгоград,Краснодар,Саратов,Тюмень,"
    "Тольятти,Ижевск,Барнаул,Ульяновск,Иркутск,Хабаровск,Ярославль,Владивосток,Махачкала,"
    "Томск,Оренбург,Кемерово,Новокузнецк,Рязань,Астрахань,Пенза,Липецк,Тула,Киров,Чебоксары,"
    "Балашиха,Калининград,Курск,Севастополь,Сочи,Ставрополь,Улан-Удэ,Тверь,Магнитогорск,"
    "Иваново,Брянск,Белгород"
).split(",")


def _extract_indexes(text: str, upper_bound: int) -> list[int]:
    numbers = [int(num) for num in re.findall(r"\d+", text)]
    seen: set[int] = set()
    indexes: list[int] = []
    for number in numbers:
        idx = number - 1
        if 0 <= idx < upper_bound and idx not in seen:
            seen.add(idx)
            indexes.append(idx)
    return indexes


def _extract_first_int(text: str) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _normalize_geo_type(raw_text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", raw_text.strip().lower())
    return GEO_ALIASES.get(normalized) or GEO_ALIASES.get(normalized.replace("тип", "").strip())


def _extract_cities(text: str) -> list[str]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return []

    # Allow natural requests like "сам сгенерируй города, 50 самых крупных".
    if "сгенер" in normalized and "город" in normalized:
        requested = _extract_first_int(normalized) or 10
        count = max(1, min(requested, len(AUTO_CITIES)))
        return AUTO_CITIES[:count]

    # Support comma and semicolon separated inputs.
    chunks = re.split(r"[;,]", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _geo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="city"), KeyboardButton(text="metro")],
            [KeyboardButton(text="district"), KeyboardButton(text="address")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdGenerationStates.waiting_niche)
    await message.answer(
        "Привет! Я помогу собрать пачку Avito-объявлений в Excel.\n\n"
        "Шаг 1/5: отправьте нишу или услугу (например: услуги авитолога).",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AdGenerationStates.waiting_niche)
async def receive_niche(message: Message, state: FSMContext, jtbd_agent: JTBDAgent) -> None:
    niche = (message.text or "").strip()
    if not niche:
        await message.answer("Ниша не должна быть пустой. Напишите одним сообщением, что продвигаем.")
        return

    try:
        segments_data = await asyncio.to_thread(jtbd_agent.generate_segments, niche)
        segments = [str(item.get("segment", "")).strip() for item in segments_data if item.get("segment")]
        if not segments:
            raise ValueError("No segments generated")
    except Exception as exc:  # noqa: BLE001
        logger.exception("JTBD generation failed")
        await message.answer(f"Ошибка генерации сегментов: {exc}")
        return

    await state.update_data(niche=niche, segments=segments)
    await state.set_state(AdGenerationStates.waiting_segment_selection)

    indexed = "\n".join([f"{i + 1}. {seg}" for i, seg in enumerate(segments)])
    await message.answer("Шаг 2/5: выберите сегменты.\nМожно так: 1,3 или 1 и 3.\n\n" + indexed)


@router.message(AdGenerationStates.waiting_segment_selection)
async def receive_segments(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    segments: list[str] = data.get("segments", [])

    indexes = _extract_indexes(message.text or "", len(segments))
    chosen = [segments[i] for i in indexes]

    if not chosen:
        await message.answer("Не понял номера сегментов. Пример: 1,3 или 2 и 5.")
        return

    await state.update_data(selected_segments=chosen)
    await state.set_state(AdGenerationStates.waiting_ads_count)
    chosen_pretty = "\n".join([f"• {segment}" for segment in chosen])
    await message.answer(
        "Шаг 3/5: сколько объявлений нужно?\nВведите число от 1 до 300.\n\n"
        f"Вы выбрали сегменты:\n{chosen_pretty}"
    )


@router.message(AdGenerationStates.waiting_ads_count)
async def receive_ads_count(message: Message, state: FSMContext) -> None:
    count = _extract_first_int((message.text or "").strip())
    if count is None or count <= 0 or count > 300:
        await message.answer("Введите число от 1 до 300.")
        return

    await state.update_data(ads_count=count)
    await state.set_state(AdGenerationStates.waiting_cities)
    await message.answer(
        "Шаг 4/5: введите города через запятую.\n"
        "Например: Москва, Санкт-Петербург\n\n"
        "Или напишите: «сгенерируй города, 20 самых крупных».",
    )


@router.message(AdGenerationStates.waiting_cities)
async def receive_cities(message: Message, state: FSMContext) -> None:
    cities = _extract_cities(message.text or "")
    if not cities:
        await message.answer("Список городов пуст. Попробуйте снова.")
        return

    await state.update_data(cities=cities)
    await state.set_state(AdGenerationStates.waiting_geo_type)
    cities_preview = ", ".join(cities[:5]) + ("..." if len(cities) > 5 else "")
    await message.answer(
        "Шаг 5/5: выберите тип GEO:\ncity / metro / district / address\n\n"
        f"Города: {cities_preview}",
        reply_markup=_geo_keyboard(),
    )


@router.message(AdGenerationStates.waiting_geo_type, F.text)
async def receive_geo_type(message: Message, state: FSMContext, orchestrator: AdsOrchestrator) -> None:
    geo_type = _normalize_geo_type(message.text or "")
    if geo_type not in ALLOWED_GEO:
        await message.answer("Некорректный GEO. Используйте: city / metro / district / address")
        return

    data: dict[str, Any] = await state.get_data()
    config = GenerationConfig(
        niche=data["niche"],
        selected_segments=data["selected_segments"],
        cities=data["cities"],
        geo_type=geo_type,
        ads_count=data["ads_count"],
    )

    await message.answer("Запускаю генерацию... Это может занять до 1-2 минут.", reply_markup=ReplyKeyboardRemove())

    try:
        rows = await asyncio.to_thread(orchestrator.generate_ads, config, generate_geo)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            file_path = await asyncio.to_thread(export_ads_to_excel, rows, tmp.name)
        await message.answer_document(
            FSInputFile(file_path),
            caption=f"Готово! Сгенерировано объявлений: {len(rows)}",
        )
        try:
            os.unlink(file_path)
        except OSError:
            logger.warning("Failed to remove temporary xlsx file: %s", file_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ad generation failed")
        await message.answer(f"Ошибка генерации: {exc}")

    await state.clear()
