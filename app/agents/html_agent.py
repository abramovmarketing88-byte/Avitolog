from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt
from app.utils.text_utils import one_line_html


class HTMLAgent:
    def __init__(self, openai_service: OpenAIService, temperature: float, assistant_id: str = ""):
        self.openai_service = openai_service
        self.temperature = temperature
        self.system_prompt = load_prompt("html.txt")
        self.assistant_id = assistant_id.strip()

    def generate_html(self, niche: str, segment: str, title: str, city: str, geo_phrase: str) -> str:
        user_prompt = (
            "Сгенерируй HTML-описание строго в 1 строку. "
            "Смысл должен соответствовать заголовку. "
            f"Ниша: {niche}. Сегмент: {segment}. Заголовок: {title}. Город: {city}. Гео: {geo_phrase}."
        )
        html = self.openai_service.generate_text(
            self.system_prompt,
            user_prompt,
            self.temperature,
            assistant_id=self.assistant_id or None,
        )
        return one_line_html(html)

    def generate_html_template(self, niche: str, segment: str) -> str:
        user_prompt = (
            "Сгенерируй один универсальный HTML-шаблон объявления в 1 строку со спинтаксисом. "
            "Используй плейсхолдеры {{TITLE}}, {{CITY}}, {{GEO}} внутри текста. "
            f"Ниша: {niche}. Сегмент: {segment}. "
            "Итоговый текст после подстановки и разворачивания спинтакса должен быть около 180-220 слов. "
            "Сделай структуру: сильный оффер, подробное описание пользы, список из 5-7 пунктов, "
            "снятие возражений и CTA. Верни только HTML."
        )
        html = self.openai_service.generate_text(
            self.system_prompt,
            user_prompt,
            temperature=min(self.temperature, 0.3),
            assistant_id=self.assistant_id or None,
        )
        return one_line_html(html)
