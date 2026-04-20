from typing import Any

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt


class InputParserAgent:
    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service
        self.system_prompt = load_prompt("input_parser.txt")

    def parse(self, text: str) -> dict[str, Any]:
        user_prompt = (
            "Извлеки структуру из пользовательского ввода.\n"
            f"Ввод: {text}\n"
            "Верни только JSON по формату из system prompt."
        )
        result = self.openai_service.generate_json(self.system_prompt, user_prompt, temperature=0)
        if not isinstance(result, dict):
            return {}
        return result
