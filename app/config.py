import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    bot_token: str
    openai_model: str = "gpt-4o-mini"
    default_temperature: float = 0.7
    max_retries: int = 3

    @staticmethod
    def from_env() -> "Settings":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        default_temperature = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
        max_retries = int(os.getenv("MAX_RETRIES", "3"))

        return Settings(
            openai_api_key=openai_api_key,
            bot_token=bot_token,
            openai_model=openai_model,
            default_temperature=default_temperature,
            max_retries=max_retries,
        )
