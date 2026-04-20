import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

"""Simple script to generate 10 ads and print output."""

from app.agents.copy_agent import CopyAgent
from app.agents.html_agent import HTMLAgent
from app.services.geo_service import generate_geo
from app.services.openai_service import OpenAIService
from app.services.orchestrator import AdsOrchestrator, GenerationConfig


def main() -> None:
    service = OpenAIService(api_key="test", model="gpt-4.1-mini", max_retries=1)

    class StubCopyAgent(CopyAgent):
        def generate_title(self, niche: str, segment: str, city: str, geo_phrase: str) -> str:
            return f"{segment} {niche} {city}"[:50]

    class StubHTMLAgent(HTMLAgent):
        def generate_html(self, niche: str, segment: str, title: str, city: str, geo_phrase: str) -> str:
            return f"<p><strong>{title}</strong><br>{niche} для {segment} {geo_phrase}</p>"

    orchestrator = AdsOrchestrator(copy_agent=StubCopyAgent(service, 0.1), html_agent=StubHTMLAgent(service, 0.1))

    config = GenerationConfig(
        niche="Продвижение на Avito",
        selected_segments=["Малый бизнес", "Новички"],
        cities=["Москва", "Казань"],
        geo_type="city",
        ads_count=10,
    )

    rows = orchestrator.generate_ads(config, generate_geo)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
