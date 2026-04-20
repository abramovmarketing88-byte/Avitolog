import logging
from typing import Any

from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


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
        try:
            # Lower temperature for strict JSON structure and stable schema.
            result = self.openai_service.generate_json(self.system_prompt, user_prompt, min(self.temperature, 0.2))
            if isinstance(result, dict):
                for key in ("segments", "data", "items", "result"):
                    candidate = result.get(key)
                    if isinstance(candidate, list):
                        result = candidate
                        break

            cleaned: list[dict[str, Any]] = []
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and item.get("segment"):
                        cleaned.append(item)
            if cleaned:
                return cleaned
        except Exception as exc:  # noqa: BLE001
            logger.warning("JTBD JSON parse fallback activated: %s", exc)

        return self._fallback_segments(niche)

    @staticmethod
    def _fallback_segments(niche: str) -> list[dict[str, Any]]:
        return [
            {
                "segment": "Новички на Avito",
                "jtbd": f"Запустить {niche} и получить первые заявки",
                "motivation": "Быстро начать продажи",
                "barriers": ["Нет опыта", "Страх слить бюджет"],
                "triggers": ["Понятный план", "Быстрый старт"],
            },
            {
                "segment": "Занятые предприниматели",
                "jtbd": f"Получать заявки по {niche} без микроменеджмента",
                "motivation": "Экономия времени",
                "barriers": ["Нехватка времени", "Недоверие подрядчикам"],
                "triggers": ["Прозрачная отчетность", "Работа под ключ"],
            },
            {
                "segment": "Продавцы с действующими объявлениями",
                "jtbd": "Повысить отклик и конверсию текущих объявлений",
                "motivation": "Увеличить поток лидов",
                "barriers": ["Слабые тексты", "Низкий CTR"],
                "triggers": ["Понятные улучшения", "Быстрый рост метрик"],
            },
            {
                "segment": "Малый бизнес с ограниченным бюджетом",
                "jtbd": "Снизить стоимость заявки и повысить рентабельность",
                "motivation": "Получать больше лидов за те же деньги",
                "barriers": ["Ограниченный бюджет", "Сомнения в окупаемости"],
                "triggers": ["Прогнозируемый результат", "Поэтапные тесты"],
            },
            {
                "segment": "Клиенты после блокировок/снижения охвата",
                "jtbd": "Восстановить стабильный поток заявок",
                "motivation": "Вернуть продажи",
                "barriers": ["Негативный опыт", "Риск повторных проблем"],
                "triggers": ["Безопасная стратегия", "Контроль рисков"],
            },
        ]
