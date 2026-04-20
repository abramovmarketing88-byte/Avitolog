import json

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt


class CopyAgent:
    def __init__(self, openai_service: OpenAIService, temperature: float):
        self.openai_service = openai_service
        self.temperature = temperature
        self.system_prompt = load_prompt("ctr.txt")

    def generate_title(self, niche: str, segment: str, city: str, geo_phrase: str) -> str:
        user_prompt = (
            "Сгенерируй 1 заголовок для Avito длиной до 50 символов. "
            "Строго верни JSON: {\"title\": \"...\"}. "
            f"Ниша: {niche}. Сегмент: {segment}. Город: {city}. Гео-фраза: {geo_phrase}."
        )
        text = self.openai_service.generate_text(self.system_prompt, user_prompt, self.temperature)
        try:
            parsed = json.loads(text)
            return str(parsed["title"]).strip()
        except Exception:  # noqa: BLE001
            return text.strip().splitlines()[0].strip('" ')
