import itertools
import random
from dataclasses import dataclass

from app.agents.copy_agent import CopyAgent
from app.agents.html_agent import HTMLAgent
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

        distribution = itertools.cycle(list(itertools.product(config.selected_segments, config.cities)))

        for _ in range(config.ads_count):
            segment, city = next(distribution)
            geo_ctx = geo_provider(city, config.geo_type)

            title = self._generate_unique_title(config.niche, segment, city, geo_ctx.geo_phrase, used_titles)
            description = self._generate_valid_html(config.niche, segment, title, city, geo_ctx.geo_phrase)

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

    def _generate_unique_title(self, niche: str, segment: str, city: str, geo_phrase: str, used_titles: list[str]) -> str:
        fallback_counter = 1
        for _ in range(5):
            candidate = truncate_title(self.copy_agent.generate_title(niche, segment, city, geo_phrase), 50)
            if not candidate:
                continue
            if candidate in used_titles:
                continue
            if any(similarity(candidate, existing) > 0.88 for existing in used_titles):
                continue
            return candidate

        while True:
            fallback = truncate_title(f"{segment}: {niche} {fallback_counter}")
            fallback_counter += 1
            if fallback not in used_titles:
                return fallback

    def _generate_valid_html(self, niche: str, segment: str, title: str, city: str, geo_phrase: str) -> str:
        for _ in range(3):
            html = self.html_agent.generate_html(niche, segment, title, city, geo_phrase)
            html = one_line_html(html)
            if "\n" not in html and html and len(html) > 20:
                return html
        return f"<p><strong>{title}</strong><br>Услуга {niche} {geo_phrase}. Напишите для расчета.</p>"
