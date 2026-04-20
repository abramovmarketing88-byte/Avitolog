import json
import logging
import re
import time
from typing import Any

from openai import OpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, api_key: str, model: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        assistant_id: str | None = None,
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if assistant_id:
                    try:
                        response = self.client.responses.create(
                            model=self.model,
                            assistant_id=assistant_id,
                            temperature=temperature,
                            input=user_prompt,
                        )
                    except Exception as assistant_exc:  # noqa: BLE001
                        logger.warning(
                            "Assistant call failed, fallback to system prompt mode. assistant_id=%s error=%s",
                            assistant_id,
                            assistant_exc,
                        )
                        response = self.client.responses.create(
                            model=self.model,
                            temperature=temperature,
                            input=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        )
                else:
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

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        assistant_id: str | None = None,
    ) -> Any:
        text = self.generate_text(system_prompt, user_prompt, temperature, assistant_id=assistant_id)
        if not text.strip():
            raise ValueError("Model returned empty JSON response")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL)
            if fenced:
                return json.loads(fenced.group(1))

            # Tolerate wrappers around JSON and try both object and array payloads.
            obj_start = text.find("{")
            obj_end = text.rfind("}")
            if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
                return json.loads(text[obj_start : obj_end + 1])

            arr_start = text.find("[")
            arr_end = text.rfind("]")
            if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
                return json.loads(text[arr_start : arr_end + 1])
            raise
