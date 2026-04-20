from typing import Any

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt


class InputParserAgent:
    def __init__(self, openai_service: OpenAIService, assistant_id: str = ""):
        self.openai_service = openai_service
        self.system_prompt = load_prompt("input_parser.txt")
        self.assistant_id = assistant_id.strip()

    def parse(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        user_prompt = (
            "Извлеки структуру из пользовательского ввода с учетом текущего шага и уже известных данных.\n"
            f"Контекст: {context}\n"
            f"Ввод: {text}\n"
            "Верни только JSON по формату из system prompt."
        )
        result = self.openai_service.generate_json(
            self.system_prompt,
            user_prompt,
            temperature=0,
            assistant_id=self.assistant_id or None,
        )
        if not isinstance(result, dict):
            return {}
        return result
