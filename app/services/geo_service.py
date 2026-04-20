import random
from dataclasses import dataclass


@dataclass(frozen=True)
class GeoContext:
    city: str
    geo_type: str
    geo_phrase: str


_METRO_BY_CITY = {
    "москва": ["метро Таганская", "метро Белорусская", "метро ВДНХ"],
    "санкт-петербург": ["метро Невский проспект", "метро Московская", "метро Парнас"],
}

_DISTRICTS = {
    "москва": ["район Таганка", "район Хамовники", "район Марьино"],
    "санкт-петербург": ["район Петроградка", "район Купчино", "район Колпино"],
}


def _city_phrases(city: str) -> list[str]:
    return [f"в {city}", f"по {city}", f"рядом с вами в {city}"]


def generate_geo(city: str, geo_type: str) -> GeoContext:
    normalized = city.strip()
    key = normalized.lower()

    if geo_type == "metro":
        points = _METRO_BY_CITY.get(key) or [f"метро в {normalized}"]
        geo_phrase = random.choice(points)
    elif geo_type == "district":
        points = _DISTRICTS.get(key) or [f"район {normalized}"]
        geo_phrase = random.choice(points)
    elif geo_type == "address":
        geo_phrase = f"адрес в {normalized} уточняется"
    else:
        geo_phrase = random.choice(_city_phrases(normalized))

    return GeoContext(city=normalized, geo_type=geo_type, geo_phrase=geo_phrase)
