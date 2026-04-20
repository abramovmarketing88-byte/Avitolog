import itertools
import random
import re
from dataclasses import dataclass

from app.agents.copy_agent import CopyAgent
from app.agents.html_agent import HTMLAgent
from app.utils.spintax_utils import expand_spintax
from app.utils.text_utils import one_line_html, similarity, truncate_title


@dataclass
class GenerationConfig:
    niche: str
    selected_segments: list[str]
    cities: list[str]
    geo_type: str
    ads_count: int


class AdsOrchestrator:
    def __init__(self, copy_agent: CopyAgent, html_agent: HTMLAgent):
        self.copy_agent = copy_agent
        self.html_agent = html_agent

    def generate_ads(self, config: GenerationConfig, geo_provider) -> list[dict]:
        if config.ads_count <= 0:
            raise ValueError("ads_count must be greater than 0")
        if not config.selected_segments:
            raise ValueError("selected_segments cannot be empty")
        if not config.cities:
            raise ValueError("cities cannot be empty")

        rows: list[dict] = []
        used_titles: list[str] = []
        title_pools = {
            segment: self.copy_agent.generate_title_pack(config.niche, segment, size=24)
            for segment in config.selected_segments
        }
        html_templates = {
            segment: self._generate_html_template(config.niche, segment)
            for segment in config.selected_segments
        }
        title_cursor = {segment: 0 for segment in config.selected_segments}

        distribution = itertools.cycle(list(itertools.product(config.selected_segments, config.cities)))

        for _ in range(config.ads_count):
            segment, city = next(distribution)
            geo_ctx = geo_provider(city, config.geo_type)

            title = self._generate_unique_title_from_pool(
                niche=config.niche,
                segment=segment,
                city=geo_ctx.city,
                geo_phrase=geo_ctx.geo_phrase,
                used_titles=used_titles,
                title_pool=title_pools.get(segment, []),
                cursor=title_cursor,
            )
            description = self._render_from_template(
                template=html_templates.get(segment, ""),
                title=title,
                city=geo_ctx.city,
                geo_phrase=geo_ctx.geo_phrase,
                niche=config.niche,
            )

            rows.append(
                {
                    "title": title,
                    "description": description,
                    "city": geo_ctx.city,
                    "geo": geo_ctx.geo_phrase,
                    "segment": segment,
                }
            )
            used_titles.append(title)

        random.shuffle(rows)
        return rows

    def _generate_unique_title_from_pool(
        self,
        niche: str,
        segment: str,
        city: str,
        geo_phrase: str,
        used_titles: list[str],
        title_pool: list[str],
        cursor: dict[str, int],
    ) -> str:
        fallback_counter = 1
        local_pool = title_pool or [f"{niche}: больше заявок и клиентов"]
        for _ in range(max(8, len(local_pool))):
            idx = cursor[segment] % len(local_pool)
            cursor[segment] += 1
            base = local_pool[idx]
            candidate = truncate_title(
                base.replace("{{CITY}}", city).replace("{{GEO}}", geo_phrase).replace("{{NICHE}}", niche),
                50,
            )
            if not candidate:
                continue
            if candidate in used_titles:
                continue
            if any(similarity(candidate, existing) > 0.88 for existing in used_titles):
                continue
            return candidate

        while True:
            fallback_templates = [
                f"{niche}: больше заявок и продаж",
                f"{niche}: стабильный поток клиентов",
                f"{niche}: усилим отклик объявлений",
                f"{niche}: запуск с понятным планом",
                f"{niche}: рост конверсии без хаоса",
                f"{niche}: приводим целевые обращения",
            ]
            fallback = truncate_title(fallback_templates[(fallback_counter - 1) % len(fallback_templates)])
            fallback_counter += 1
            if fallback not in used_titles:
                return fallback

    def _generate_html_template(self, niche: str, segment: str) -> str:
        for _ in range(3):
            html = self.html_agent.generate_html_template(niche, segment)
            html = one_line_html(html)
            if "\n" not in html and html and len(html) > 20:
                return html
        return (
            "<p><strong>{{TITLE}}</strong><br>{Если вы ищете {{NICHE}} в {{CITY}}, мы подготовим для вас понятный и рабочий план запуска без лишней теории.|Нужны {{NICHE}} {{GEO}} с измеримым результатом? Покажем, как получить больше целевых обращений и не сливать бюджет.}"
            "<br>{Мы берем на себя аудит текущей ситуации, приоритизацию гипотез и пошаговую реализацию, чтобы вы видели прогресс уже в первые недели.|Работаем системно: анализируем текущие объявления, усиливаем оффер, убираем слабые места и доводим до стабильного потока заявок.}"
            "<br>{Вы получаете не просто тексты, а структуру, которая помогает превращать просмотры в обращения и обращения в продажи.|Наша задача — сделать так, чтобы ваше предложение выглядело сильнее конкурентов и давало понятную выгоду клиенту.}</p>"
            "<p><strong>{Что входит в работу|Как устроен процесс}</strong></p>"
            "<ul><li>{Разбор ниши, конкурентов и спроса по региону.|Анализ целевой аудитории и поведения покупателей в категории.}</li>"
            "<li>{Упаковка оффера: выгоды, триггеры доверия, снятие возражений.|Формулировка понятного ценностного предложения под реальный спрос.}</li>"
            "<li>{Оптимизация заголовков и описаний под конверсию.|Переписывание ключевых блоков карточки для роста отклика.}</li>"
            "<li>{Проверка гипотез и улучшение по метрикам.|Пошаговые итерации с опорой на результат, а не на догадки.}</li>"
            "<li>{Рекомендации по фото, цене и обработке чатов.|Практические действия, которые влияют на решение клиента.}</li></ul>"
            "<p><strong>{Почему это выгодно|Что вы получите на выходе}</strong><br>{Прозрачный процесс, понятные шаги, фокус на окупаемость и качество лидов.|Системную работу под ваш сегмент, чтобы снизить хаос и увеличить предсказуемость продаж.}"
            "<br>{Напишите нам сегодня — подготовим персональный план запуска под ваш бизнес и текущие задачи.|Оставьте сообщение, и мы предложим приоритетные действия именно для вашей ситуации.}</p>"
        )

    def _render_from_template(self, template: str, title: str, city: str, geo_phrase: str, niche: str) -> str:
        rendered = expand_spintax(template)
        rendered = (
            rendered.replace("{{TITLE}}", title)
            .replace("{{CITY}}", city)
            .replace("{{GEO}}", geo_phrase)
            .replace("{{NICHE}}", niche)
        )
        rendered = one_line_html(rendered)
        if "\n" not in rendered and rendered and len(rendered) > 20 and self._word_count(rendered) >= 160:
            return rendered
        return self._expanded_fallback_html(title=title, niche=niche, city=city, geo_phrase=geo_phrase)

    @staticmethod
    def _word_count(html_text: str) -> int:
        plain = re.sub(r"<[^>]+>", " ", html_text)
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", plain)
        return len(words)

    @staticmethod
    def _expanded_fallback_html(title: str, niche: str, city: str, geo_phrase: str) -> str:
        return one_line_html(
            f"<p><strong>{title}</strong><br>"
            f"Если вам нужны {niche} в {city}, мы помогаем выстроить понятный и управляемый путь к заявкам без хаотичных действий. "
            f"Наша работа начинается с диагностики текущей ситуации: что уже сделано, где теряются клиенты и какие шаги дадут результат быстрее всего. "
            f"Мы учитываем специфику {geo_phrase}, поведение аудитории и конкуренцию в категории, чтобы вы получили не шаблон, а прикладное решение."
            f"<br>Дальше формируем структуру объявления: сильный оффер, конкретная выгода, понятные аргументы, честные формулировки и призыв к действию, который реально работает.</p>"
            f"<p><strong>Что входит в работу</strong></p>"
            f"<ul>"
            f"<li>Анализ ниши, конкурентов и текущих объявлений.</li>"
            f"<li>Усиление заголовков и описаний под реальную конверсию.</li>"
            f"<li>Снижение слабых мест в оффере и коммуникации с клиентом.</li>"
            f"<li>Пошаговый план улучшений с приоритетами и логикой внедрения.</li>"
            f"<li>Рекомендации по упаковке, цене и обработке входящих сообщений.</li>"
            f"<li>Фокус на качественных лидах, а не на пустых просмотрах.</li>"
            f"</ul>"
            f"<p><strong>Почему это выгодно</strong><br>"
            f"Вы получаете прозрачный процесс, понятные действия и измеримый прогресс без лишней теории. "
            f"Мы работаем в практическом формате: короткие итерации, быстрые правки, акцент на то, что действительно влияет на отклик и продажи. "
            f"Если вам важно получить стабильный поток обращений по направлению {niche}, напишите нам — подготовим персональный план и начнем с самых результативных шагов.</p>"
        )
