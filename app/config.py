import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

DEFAULT_ASSISTANT_ID = "asst_ochis2TU72Qcdg5bEEHYfAMk"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    bot_token: str
    assistant_id: str
    max_retries: int = 3
    user_message_suffix: str = ""

    @staticmethod
    def from_env() -> "Settings":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        assistant_id = os.getenv("ASSISTANT_ID", DEFAULT_ASSISTANT_ID).strip()
        max_retries = int(os.getenv("MAX_RETRIES", "3"))
        user_message_suffix = os.getenv("USER_MESSAGE_SUFFIX", "").strip()

        return Settings(
            openai_api_key=openai_api_key,
            bot_token=bot_token,
            assistant_id=assistant_id,
            max_retries=max_retries,
            user_message_suffix=user_message_suffix,
        )
