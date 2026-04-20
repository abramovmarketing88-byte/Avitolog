import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.agents.copy_agent import CopyAgent
from app.agents.html_agent import HTMLAgent
from app.agents.input_parser_agent import InputParserAgent
from app.agents.jtbd_agent import JTBDAgent
from app.bot.handlers import router
from app.config import Settings
from app.services.openai_service import OpenAIService
from app.services.orchestrator import AdsOrchestrator

logger = logging.getLogger(__name__)


def _mask_assistant_id(value: str) -> str:
    if not value:
        return "no"
    return f"yes ({value[:12]}...)"


def create_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    openai_service = OpenAIService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.max_retries,
    )

    jtbd_agent = JTBDAgent(
        openai_service,
        temperature=settings.default_temperature,
        assistant_id=settings.assistant_jtbd_parser_id,
    )
    input_parser_agent = InputParserAgent(
        openai_service,
        assistant_id=settings.assistant_jtbd_parser_id,
    )
    copy_agent = CopyAgent(
        openai_service,
        temperature=settings.default_temperature,
        assistant_id=settings.assistant_creative_builder_id,
    )
    html_agent = HTMLAgent(
        openai_service,
        temperature=settings.default_temperature,
        assistant_id=settings.assistant_spintax_html_id or settings.assistant_creative_builder_id,
    )
    orchestrator = AdsOrchestrator(copy_agent=copy_agent, html_agent=html_agent)

    logger.info(
        "Assistants config: jtbd_parser=%s creative_builder=%s spintax_html=%s",
        _mask_assistant_id(settings.assistant_jtbd_parser_id),
        _mask_assistant_id(settings.assistant_creative_builder_id),
        _mask_assistant_id(settings.assistant_spintax_html_id or settings.assistant_creative_builder_id),
    )

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()

    dp["jtbd_agent"] = jtbd_agent
    dp["input_parser_agent"] = input_parser_agent
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    return bot, dp
