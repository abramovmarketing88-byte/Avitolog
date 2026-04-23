import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.bot.handlers import router
from app.config import Settings
from app.services.openai_service import OpenAIService


logger = logging.getLogger(__name__)


def create_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    openai_service = OpenAIService(
        api_key=settings.openai_api_key,
        max_retries=settings.max_retries,
    )

    logger.info("Using assistant id prefix: %s...", settings.assistant_id[:16])

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp["openai_service"] = openai_service
    dp["assistant_id"] = settings.assistant_id
    dp["user_message_suffix"] = settings.user_message_suffix
    dp.include_router(router)

    return bot, dp
