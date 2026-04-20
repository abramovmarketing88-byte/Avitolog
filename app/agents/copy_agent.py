import json

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt


class CopyAgent:
    def __init__(self, openai_service: OpenAIService, temperature: float, assistant_id: str = ""):
        self.openai_service = openai_service
        self.temperature = temperature
        self.system_prompt = load_prompt("ctr.txt")
        self.assistant_id = assistant_id.strip()

    def generate_title(self, niche: str, segment: str, city: str, geo_phrase: str) -> str:
        user_prompt = (
            "Сгенерируй 1 заголовок для Avito длиной до 50 символов. "
            "Строго верни JSON: {\"title\": \"...\"}. "
            f"Ниша: {niche}. Сегмент: {segment}. Город: {city}. Гео-фраза: {geo_phrase}."
        )
        text = self.openai_service.generate_text(
            self.system_prompt,
            user_prompt,
            self.temperature,
            assistant_id=self.assistant_id or None,
        )
        try:
            parsed = json.loads(text)
            return str(parsed["title"]).strip()
        except Exception:  # noqa: BLE001
            return text.strip().splitlines()[0].strip('" ')

    def generate_title_pack(self, niche: str, segment: str, size: int = 20) -> list[str]:
        user_prompt = (
            f"Сгенерируй {size} уникальных заголовков для Avito длиной до 50 символов. "
            "Верни только JSON-объект: {\"titles\": [\"...\", \"...\"]}. "
            f"Ниша: {niche}. Сегмент: {segment}. "
            "Без кликбейта, CAPS и ложных обещаний."
        )
        try:
            payload = self.openai_service.generate_json(
                self.system_prompt,
                user_prompt,
                temperature=min(self.temperature, 0.3),
                assistant_id=self.assistant_id or None,
            )
            titles: list[str] = []
            if isinstance(payload, dict) and isinstance(payload.get("titles"), list):
                for item in payload["titles"]:
                    if isinstance(item, str):
                        title = item.strip()
                        if title and title not in titles:
                            titles.append(title)
            if titles:
                return titles
        except Exception:  # noqa: BLE001
            pass

        return [
            f"{segment}: {niche}",
            f"{niche} под {segment.lower()}",
            f"{niche} для сегмента {segment.lower()}",
            f"{niche}: помощь для {segment.lower()}",
            f"{segment}: {niche} без лишних затрат",
        ]
