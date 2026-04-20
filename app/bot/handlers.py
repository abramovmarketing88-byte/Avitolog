import logging
import tempfile
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.agents.jtbd_agent import JTBDAgent
from app.services.excel_service import export_ads_to_excel
from app.services.geo_service import generate_geo
from app.services.orchestrator import AdsOrchestrator, GenerationConfig
from app.bot.states import AdGenerationStates


logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdGenerationStates.waiting_niche)
    await message.answer("Привет! Введите нишу/услугу для генерации объявлений.")


@router.message(AdGenerationStates.waiting_niche)
async def receive_niche(message: Message, state: FSMContext, jtbd_agent: JTBDAgent) -> None:
    niche = (message.text or "").strip()
    if not niche:
        await message.answer("Ниша не должна быть пустой. Попробуйте снова.")
        return

    try:
        segments_data = jtbd_agent.generate_segments(niche)
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
    await message.answer(
        "Выберите сегменты, отправьте номера через запятую (например: 1,3):\n\n" + indexed
    )


@router.message(AdGenerationStates.waiting_segment_selection)
async def receive_segments(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    segments: list[str] = data.get("segments", [])

    try:
        indexes = [int(x.strip()) - 1 for x in (message.text or "").split(",") if x.strip()]
        chosen = [segments[i] for i in indexes if 0 <= i < len(segments)]
    except ValueError:
        chosen = []

    if not chosen:
        await message.answer("Не удалось распознать сегменты. Укажите номера через запятую.")
        return

    await state.update_data(selected_segments=chosen)
    await state.set_state(AdGenerationStates.waiting_ads_count)
    await message.answer("Сколько объявлений нужно сгенерировать?")


@router.message(AdGenerationStates.waiting_ads_count)
async def receive_ads_count(message: Message, state: FSMContext) -> None:
    try:
        count = int((message.text or "").strip())
        if count <= 0 or count > 300:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 300.")
        return

    await state.update_data(ads_count=count)
    await state.set_state(AdGenerationStates.waiting_cities)
    await message.answer("Введите города через запятую (например: Москва, Санкт-Петербург).")


@router.message(AdGenerationStates.waiting_cities)
async def receive_cities(message: Message, state: FSMContext) -> None:
    cities = [c.strip() for c in (message.text or "").split(",") if c.strip()]
    if not cities:
        await message.answer("Список городов пуст. Попробуйте снова.")
        return

    await state.update_data(cities=cities)
    await state.set_state(AdGenerationStates.waiting_geo_type)
    await message.answer("Выберите тип GEO: city / metro / district / address")


@router.message(AdGenerationStates.waiting_geo_type, F.text)
async def receive_geo_type(message: Message, state: FSMContext, orchestrator: AdsOrchestrator) -> None:
    geo_type = (message.text or "").strip().lower()
    if geo_type not in {"city", "metro", "district", "address"}:
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

    await message.answer("Генерация запущена, это может занять до минуты...")

    try:
        rows = orchestrator.generate_ads(config, generate_geo)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            file_path = export_ads_to_excel(rows, tmp.name)
        await message.answer_document(FSInputFile(file_path), caption="Готово! Excel файл с объявлениями.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ad generation failed")
        await message.answer(f"Ошибка генерации: {exc}")

    await state.clear()
