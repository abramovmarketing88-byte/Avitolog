import asyncio
import logging
import os
import re
import tempfile
from difflib import SequenceMatcher
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.agents.jtbd_agent import JTBDAgent
from app.agents.input_parser_agent import InputParserAgent
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
CONFIRM_TEXT = "✅ Подтвердить"
EDIT_TEXT = "✏️ Изменить параметры"


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


def _looks_like_niche_reset(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    triggers = ("назад", "заново", "друг", "смен", "надо", "не это", "другая ниша", "другая услуга")
    return any(trigger in normalized for trigger in triggers)


def _normalize_niche_candidate(text: str) -> str:
    value = (text or "").strip()
    value = re.sub(r"(?i)\b(давай|назад|заново|нужно|надо|хочу|сделай|поменяй|смени)\b", " ", value)
    value = re.sub(r"[,:;.!?]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _safe_segment_numbers(payload: dict[str, Any], upper_bound: int) -> list[int]:
    numbers = payload.get("segment_numbers")
    if not isinstance(numbers, list):
        return []
    indexes: list[int] = []
    seen: set[int] = set()
    for value in numbers:
        if not isinstance(value, int):
            continue
        idx = value - 1
        if 0 <= idx < upper_bound and idx not in seen:
            seen.add(idx)
            indexes.append(idx)
    return indexes


def _segment_indexes_from_text(text: str, segments: list[str]) -> list[int]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return []

    tokens = [token for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9-]+", normalized) if len(token) >= 4]
    if not tokens:
        return []

    scored: list[tuple[int, float]] = []
    for idx, segment in enumerate(segments):
        segment_low = segment.lower()
        token_hits = sum(1 for token in tokens if token in segment_low)
        ratio = SequenceMatcher(None, normalized, segment_low).ratio()
        score = token_hits * 0.3 + ratio
        if token_hits >= 1 or ratio >= 0.55:
            scored.append((idx, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return []
    # If user wrote free text, pick best 1-2 segments by semantic closeness.
    return [item[0] for item in scored[:2]]


def _safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_cities(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("cities")
    if not isinstance(raw, list):
        return []
    cities: list[str] = []
    for item in raw:
        value = str(item).strip()
        if not value:
            continue
        lower = value.lower()
        # Reject meta phrases that are not city names.
        if any(token in lower for token in ("самых крупных", "крупных город", "городов", "сгенер", "топ", "штук")):
            continue
        if re.search(r"\d", value):
            continue
        cities.append(value)
    return cities


def _safe_geo(payload: dict[str, Any]) -> str | None:
    value = payload.get("geo_type")
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_GEO else None


def _is_confirm(payload: dict[str, Any], raw_text: str) -> bool:
    if payload.get("confirm") is True:
        return True
    intent = str(payload.get("intent", "")).lower()
    text = (raw_text or "").strip().lower()
    return intent == "confirm" or text in {"подтверждаю", "подтвердить", "✅ подтвердить", "ok", "да", "запустить"}


def _is_edit(payload: dict[str, Any], raw_text: str) -> bool:
    if payload.get("edit") is True:
        return True
    intent = str(payload.get("intent", "")).lower()
    text = (raw_text or "").strip().lower()
    return intent in {"edit", "restart"} or text in {"изменить", "изменить параметры", "✏️ изменить параметры", "редактировать", "начать заново"}


async def _ai_parse(input_parser_agent: InputParserAgent, text: str) -> dict[str, Any]:
    return await _ai_parse_with_context(input_parser_agent, text, context={})


async def _ai_parse_with_context(
    input_parser_agent: InputParserAgent,
    text: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    try:
        payload = await asyncio.to_thread(input_parser_agent.parse, text or "", context)
        return payload if isinstance(payload, dict) else {}
    except Exception:  # noqa: BLE001
        logger.exception("AI parsing failed")
        return {}


async def _maybe_handle_niche_override(
    *,
    payload: dict[str, Any],
    message: Message,
    state: FSMContext,
    jtbd_agent: JTBDAgent,
) -> bool:
    intent = str(payload.get("intent", "")).lower()
    candidate_niche = _safe_text(payload.get("niche")) or _normalize_niche_candidate(message.text or "")
    # Guardrail: do not treat arbitrary free text as niche override.
    # Switch niche only when AI explicitly marks set_niche or user clearly asks to reset.
    if intent != "set_niche" and not _looks_like_niche_reset(message.text or ""):
        return False
    if len(candidate_niche) < 4:
        return False

    try:
        segments_data = await asyncio.to_thread(jtbd_agent.generate_segments, candidate_niche)
        new_segments = [str(item.get("segment", "")).strip() for item in segments_data if item.get("segment")]
        if not new_segments:
            return False
        await state.update_data(niche=candidate_niche, segments=new_segments, selected_segments=[])
        await state.set_state(AdGenerationStates.waiting_segment_selection)
        indexed = "\n".join([f"{i + 1}. {seg}" for i, seg in enumerate(new_segments)])
        await message.answer(
            "Принял новую нишу и пересобрал сегменты через ИИ.\n"
            "Шаг 2/6: выберите сегменты.\nМожно так: 1,3 или 1 и 3.\n\n"
            + indexed
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to re-generate segments after set_niche intent")
        return False


def _geo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="city"), KeyboardButton(text="metro")],
            [KeyboardButton(text="district"), KeyboardButton(text="address")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CONFIRM_TEXT), KeyboardButton(text=EDIT_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _build_preview_card(data: dict[str, Any]) -> str:
    segments: list[str] = data.get("selected_segments", [])
    cities: list[str] = data.get("cities", [])
    geo_type = str(data.get("geo_type", ""))
    cities_preview = ", ".join(cities[:10]) + ("..." if len(cities) > 10 else "")
    segments_preview = "\n".join([f"• {segment}" for segment in segments]) or "—"
    return (
        "Проверьте параметры перед генерацией:\n\n"
        f"Ниша: {data.get('niche', '—')}\n"
        f"Количество объявлений: {data.get('ads_count', '—')}\n"
        f"Тип GEO: {geo_type}\n"
        f"Города ({len(cities)}): {cities_preview or '—'}\n\n"
        f"Сегменты:\n{segments_preview}\n\n"
        "Нажмите «Подтвердить», чтобы запустить генерацию."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdGenerationStates.waiting_niche)
    await message.answer(
        "Привет! Я помогу собрать пачку Avito-объявлений в Excel.\n\n"
        "Шаг 1/6: отправьте нишу или услугу (например: услуги авитолога).",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AdGenerationStates.waiting_niche)
async def receive_niche(
    message: Message,
    state: FSMContext,
    jtbd_agent: JTBDAgent,
    input_parser_agent: InputParserAgent,
) -> None:
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_niche"},
    )
    niche = _safe_text(payload.get("niche")) or (message.text or "").strip()
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
    await message.answer("Шаг 2/6: выберите сегменты.\nМожно так: 1,3 или 1 и 3.\n\n" + indexed)


@router.message(AdGenerationStates.waiting_segment_selection)
async def receive_segments(
    message: Message,
    state: FSMContext,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    data = await state.get_data()
    segments: list[str] = data.get("segments", [])
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_segment_selection", "niche": data.get("niche"), "segments": segments},
    )

    if await _maybe_handle_niche_override(payload=payload, message=message, state=state, jtbd_agent=jtbd_agent):
        return

    indexes = _safe_segment_numbers(payload, len(segments)) or _extract_indexes(message.text or "", len(segments))
    if not indexes:
        indexes = _segment_indexes_from_text(message.text or "", segments)
    if not indexes:
        indexes = []
    chosen = [segments[i] for i in indexes]

    if not chosen:
        await message.answer("Не понял выбор сегментов. Пример: 1,3 или «первый и третий».")
        return

    await state.update_data(selected_segments=chosen)
    await state.set_state(AdGenerationStates.waiting_ads_count)
    chosen_pretty = "\n".join([f"• {segment}" for segment in chosen])
    await message.answer(
        "Шаг 3/6: сколько объявлений нужно?\nВведите число от 1 до 300.\n\n"
        f"Вы выбрали сегменты:\n{chosen_pretty}"
    )


@router.message(AdGenerationStates.waiting_ads_count)
async def receive_ads_count(
    message: Message,
    state: FSMContext,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    data = await state.get_data()
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_ads_count", "niche": data.get("niche"), "selected_segments": data.get("selected_segments")},
    )
    if await _maybe_handle_niche_override(payload=payload, message=message, state=state, jtbd_agent=jtbd_agent):
        return
    parsed_count = payload.get("ads_count")
    count = parsed_count if isinstance(parsed_count, int) else _extract_first_int((message.text or "").strip())
    if count is None or count <= 0 or count > 300:
        await message.answer("Введите число от 1 до 300.")
        return

    await state.update_data(ads_count=count)
    await state.set_state(AdGenerationStates.waiting_cities)
    await message.answer(
        "Шаг 4/6: введите города через запятую.\n"
        "Например: Москва, Санкт-Петербург\n\n"
        "Или напишите: «сгенерируй города, 20 самых крупных».",
    )


@router.message(AdGenerationStates.waiting_cities)
async def receive_cities(
    message: Message,
    state: FSMContext,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    data = await state.get_data()
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_cities", "niche": data.get("niche"), "ads_count": data.get("ads_count")},
    )
    if await _maybe_handle_niche_override(payload=payload, message=message, state=state, jtbd_agent=jtbd_agent):
        return
    cities = _safe_cities(payload) or _extract_cities(message.text or "")
    if not cities:
        await message.answer("Список городов пуст. Попробуйте снова.")
        return

    await state.update_data(cities=cities)
    parsed_geo = _safe_geo(payload)
    if parsed_geo in ALLOWED_GEO:
        await state.update_data(geo_type=parsed_geo)
        data: dict[str, Any] = await state.get_data()
        await state.set_state(AdGenerationStates.waiting_confirmation)
        await message.answer("Шаг 6/6: подтверждение", reply_markup=_confirm_keyboard())
        await message.answer(_build_preview_card(data))
        return

    await state.set_state(AdGenerationStates.waiting_geo_type)
    cities_preview = ", ".join(cities[:5]) + ("..." if len(cities) > 5 else "")
    await message.answer(
        "Шаг 5/6: выберите тип GEO:\ncity / metro / district / address\n\n"
        f"Города: {cities_preview}",
        reply_markup=_geo_keyboard(),
    )


@router.message(AdGenerationStates.waiting_geo_type, F.text)
async def receive_geo_type(
    message: Message,
    state: FSMContext,
    orchestrator: AdsOrchestrator,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    data = await state.get_data()
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_geo_type", "niche": data.get("niche"), "cities": data.get("cities")},
    )
    if await _maybe_handle_niche_override(payload=payload, message=message, state=state, jtbd_agent=jtbd_agent):
        return
    geo_type = _safe_geo(payload) or _normalize_geo_type(message.text or "")
    if geo_type not in ALLOWED_GEO:
        await message.answer("Некорректный GEO. Используйте: city / metro / district / address")
        return

    await state.update_data(geo_type=geo_type)
    data: dict[str, Any] = await state.get_data()
    await state.set_state(AdGenerationStates.waiting_confirmation)
    await message.answer(
        "Шаг 6/6: подтверждение",
        reply_markup=_confirm_keyboard(),
    )
    await message.answer(_build_preview_card(data))


@router.message(AdGenerationStates.waiting_confirmation, F.text)
async def receive_confirmation(
    message: Message,
    state: FSMContext,
    orchestrator: AdsOrchestrator,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    data = await state.get_data()
    payload = await _ai_parse_with_context(
        input_parser_agent,
        message.text or "",
        context={"state": "waiting_confirmation", "data": data},
    )
    if await _maybe_handle_niche_override(payload=payload, message=message, state=state, jtbd_agent=jtbd_agent):
        return
    text = (message.text or "").strip().lower()
    if _is_confirm(payload, text):
        data = await state.get_data()
        config = GenerationConfig(
            niche=data["niche"],
            selected_segments=data["selected_segments"],
            cities=data["cities"],
            geo_type=data["geo_type"],
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
        return

    if _is_edit(payload, text):
        await state.set_state(AdGenerationStates.waiting_niche)
        await message.answer(
            "Ок, обновим параметры. Отправьте нишу заново (шаг 1/6).",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(
        "Выберите действие кнопкой: «✅ Подтвердить» или «✏️ Изменить параметры».",
        reply_markup=_confirm_keyboard(),
    )


@router.message(F.text)
async def handle_free_text_after_flow(
    message: Message,
    state: FSMContext,
    input_parser_agent: InputParserAgent,
    jtbd_agent: JTBDAgent,
) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return

    payload = await _ai_parse(input_parser_agent, message.text or "")
    niche = _safe_text(payload.get("niche"))
    if niche:
        try:
            segments_data = await asyncio.to_thread(jtbd_agent.generate_segments, niche)
            segments = [str(item.get("segment", "")).strip() for item in segments_data if item.get("segment")]
            if segments:
                await state.update_data(niche=niche, segments=segments, selected_segments=[])
                await state.set_state(AdGenerationStates.waiting_segment_selection)
                indexed = "\n".join([f"{i + 1}. {seg}" for i, seg in enumerate(segments)])
                await message.answer(
                    "Принял новую нишу и пересобрал сегменты через ИИ.\n"
                    "Шаг 2/6: выберите сегменты.\nМожно так: 1,3 или 1 и 3.\n\n"
                    + indexed
                )
                return
        except Exception:  # noqa: BLE001
            logger.exception("Free-text niche processing failed")

    text = (message.text or "").strip().lower()
    if any(phrase in text for phrase in ("снова", "ещ", "заново", "повтор", "нов")):
        await state.set_state(AdGenerationStates.waiting_niche)
        await message.answer(
            "Запускаем новый цикл.\n\nШаг 1/6: отправьте нишу или услугу.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer(
        "Готов начать новый расчет. Нажмите /start или напишите «снова».",
        reply_markup=ReplyKeyboardRemove(),
    )
