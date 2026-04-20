import json
import logging
import time
from typing import Any

from openai import OpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, api_key: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    temperature=temperature,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return (response.output_text or "").strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("OpenAI request failed on attempt %s/%s: %s", attempt, self.max_retries, exc)
                time.sleep(min(2**attempt, 8))

        raise RuntimeError(f"OpenAI generation failed after retries: {last_error}")

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float) -> Any:
        text = self.generate_text(system_prompt, user_prompt, temperature)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
