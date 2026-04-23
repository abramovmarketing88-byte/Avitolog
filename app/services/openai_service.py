import logging
import time

from openai import OpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, api_key: str, max_retries: int = 3):
        self.client = OpenAI(api_key=api_key)
        self.max_retries = max_retries

    def run_assistant(self, assistant_id: str, user_message: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._run_assistant_once(assistant_id, user_message)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "Assistant request failed on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                time.sleep(min(2**attempt, 8))

        raise RuntimeError(f"Assistant failed after retries: {last_error}")

    def _run_assistant_once(self, assistant_id: str, user_message: str) -> str:
        thread = self.client.beta.threads.create(
            messages=[{"role": "user", "content": user_message}],
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )
        started = time.time()
        timeout_sec = 180

        while True:
            run_state = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            if run_state.status == "completed":
                break
            if run_state.status in {"failed", "cancelled", "expired", "incomplete"}:
                detail = getattr(run_state, "last_error", None)
                raise RuntimeError(f"Assistant run status={run_state.status} detail={detail}")
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
