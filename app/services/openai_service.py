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
                    return self._generate_text_via_assistant(
                        assistant_id=assistant_id,
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
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

    def _generate_text_via_assistant(self, assistant_id: str, user_prompt: str, system_prompt: str) -> str:
        try:
            thread = self.client.beta.threads.create(
                messages=[{"role": "user", "content": user_prompt}],
            )
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id,
            )
            started = time.time()
            timeout_sec = 120

            while True:
                run_state = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id,
                )
                if run_state.status == "completed":
                    break
                if run_state.status in {"failed", "cancelled", "expired", "incomplete"}:
                    raise RuntimeError(f"Assistant run failed with status={run_state.status}")
                if time.time() - started > timeout_sec:
                    raise TimeoutError("Assistant run timed out")
                time.sleep(1.0)

            messages = self.client.beta.threads.messages.list(thread_id=thread.id, limit=10)
            for message in messages.data:
                if message.role != "assistant":
                    continue
                chunks: list[str] = []
                for item in message.content:
                    text_obj = getattr(item, "text", None)
                    value = getattr(text_obj, "value", None) if text_obj else None
                    if value:
                        chunks.append(value)
                if chunks:
                    return "\n".join(chunks).strip()

            raise RuntimeError("Assistant returned no text message")
        except Exception as assistant_exc:  # noqa: BLE001
            logger.warning(
                "Assistant call failed, fallback to system prompt mode. assistant_id=%s error=%s",
                assistant_id,
                assistant_exc,
            )
            response = self.client.responses.create(
                model=self.model,
                temperature=0.2,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return (response.output_text or "").strip()

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
