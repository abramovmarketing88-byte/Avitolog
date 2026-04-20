import itertools
import random
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
        local_pool = title_pool or [f"{segment}: {niche}"]
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
            fallback = truncate_title(f"{segment}: {niche} {fallback_counter}")
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
            "<p><strong>{{TITLE}}</strong><br>"
            "{Услуга {{NICHE}} {{GEO}}.|Помогаем с {{NICHE}} {{CITY}}.}"
            "</p>"
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
        if "\n" not in rendered and rendered and len(rendered) > 20:
            return rendered
        return f"<p><strong>{title}</strong><br>Услуга {niche} {geo_phrase}. Напишите для расчета.</p>"
