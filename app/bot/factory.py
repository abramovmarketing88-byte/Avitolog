from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.agents.copy_agent import CopyAgent
from app.agents.html_agent import HTMLAgent
from app.agents.jtbd_agent import JTBDAgent
from app.bot.handlers import router
from app.config import Settings
from app.services.openai_service import OpenAIService
from app.services.orchestrator import AdsOrchestrator


def create_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    openai_service = OpenAIService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.max_retries,
    )

    jtbd_agent = JTBDAgent(openai_service, temperature=settings.default_temperature)
    copy_agent = CopyAgent(openai_service, temperature=settings.default_temperature)
    html_agent = HTMLAgent(openai_service, temperature=settings.default_temperature)
    orchestrator = AdsOrchestrator(copy_agent=copy_agent, html_agent=html_agent)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()

    dp["jtbd_agent"] = jtbd_agent
    dp["orchestrator"] = orchestrator
    dp.include_router(router)

    return bot, dp
