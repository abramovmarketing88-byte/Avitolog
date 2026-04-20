from app.services.openai_service import OpenAIService
from app.utils.prompt_loader import load_prompt
from app.utils.text_utils import one_line_html


class HTMLAgent:
    def __init__(self, openai_service: OpenAIService, temperature: float):
        self.openai_service = openai_service
        self.temperature = temperature
        self.system_prompt = load_prompt("html.txt")

    def generate_html(self, niche: str, segment: str, title: str, city: str, geo_phrase: str) -> str:
        user_prompt = (
            "Сгенерируй HTML-описание строго в 1 строку. "
            "Смысл должен соответствовать заголовку. "
            f"Ниша: {niche}. Сегмент: {segment}. Заголовок: {title}. Город: {city}. Гео: {geo_phrase}."
        )
        html = self.openai_service.generate_text(self.system_prompt, user_prompt, self.temperature)
        return one_line_html(html)
