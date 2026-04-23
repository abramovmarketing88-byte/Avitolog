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

    logging.getLogger(__name__).info(
        "Avitolog bot: режим «текст объявления → ответ ассистента» (без шагов и Excel)"
    )

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not settings.assistant_id:
        raise RuntimeError("ASSISTANT_ID is not set")

    bot, dp = create_dispatcher(settings)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
