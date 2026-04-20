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
            "Без кликбейта, CAPS и ложных обещаний. "
            "Каждый заголовок должен быть понятным и предметным: что за услуга и какой результат/выгода. "
            f"Нельзя делать заголовок только названием сегмента (например: '{segment}' или '{segment}: ...')."
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
                        if self._is_usable_title(title, niche, segment) and title not in titles:
                            titles.append(title)
            if titles:
                return titles
        except Exception:  # noqa: BLE001
            pass

        return [
            f"{niche} под ключ: больше заявок",
            f"{niche}: рост отклика и продаж",
            f"{niche} с понятным планом запуска",
            f"{niche}: улучшим объявления и конверсию",
            f"{niche} без лишних затрат времени",
        ]

    @staticmethod
    def _is_usable_title(title: str, niche: str, segment: str) -> bool:
        value = " ".join(title.split())
        if not value or len(value) < 16 or len(value) > 50:
            return False

        lower = value.lower()
        lower_segment = segment.strip().lower()
        if lower == lower_segment or lower.startswith(f"{lower_segment}:"):
            return False

        niche_words = [word for word in niche.lower().split() if len(word) >= 4]
        if niche_words and not any(word in lower for word in niche_words):
            return False

        return True
