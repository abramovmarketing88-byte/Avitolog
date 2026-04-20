import asyncio
import logging

from app.bot.factory import create_dispatcher
from app.config import Settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def run() -> None:
    settings = Settings.from_env()

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    bot, dp = create_dispatcher(settings)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
