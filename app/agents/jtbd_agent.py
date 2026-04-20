from typing import Any

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt


class JTBDAgent:
    def __init__(self, openai_service: OpenAIService, temperature: float):
        self.openai_service = openai_service
        self.temperature = temperature
        self.system_prompt = load_prompt("jtbd.txt")

    def generate_segments(self, niche: str) -> list[dict[str, Any]]:
        user_prompt = (
            "Сформируй 4-6 сегментов ЦА в JSON-массиве. "
            "Каждый объект: segment, jtbd, motivation, barriers, triggers. "
            f"Ниша/услуга: {niche}."
        )
        result = self.openai_service.generate_json(self.system_prompt, user_prompt, self.temperature)
        if not isinstance(result, list):
            raise ValueError("JTBD agent returned non-list result")
        cleaned: list[dict[str, Any]] = []
        for item in result:
            if isinstance(item, dict) and item.get("segment"):
                cleaned.append(item)
        if not cleaned:
            raise ValueError("JTBD agent returned empty segments")
        return cleaned
