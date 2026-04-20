import re
from difflib import SequenceMatcher


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def truncate_title(title: str, max_length: int = 50) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    return title if len(title) <= max_length else title[: max_length - 1].rstrip() + "…"


def one_line_html(value: str) -> str:
    compact = re.sub(r"\s+", " ", value.replace("\n", " ").replace("\r", " ")).strip()
    return compact
