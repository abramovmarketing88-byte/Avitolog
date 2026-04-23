import random
import re


_SPINTAX_RE = re.compile(r"\{([^{}]+)\}")


def expand_spintax(template: str, rng: random.Random | None = None) -> str:
    rnd = rng or random.Random()
    text = template
    while True:
        match = _SPINTAX_RE.search(text)
        if not match:
            return text
        options = [item.strip() for item in match.group(1).split("|") if item.strip()]
        replacement = rnd.choice(options) if options else ""
        text = text[: match.start()] + replacement + text[match.end() :]


def generate_unique_variants(template: str, count: int) -> list[str]:
    if count <= 0:
        return []

    rnd = random.Random()
    variants: list[str] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = max(100, count * 50)

    while len(variants) < count and attempts < max_attempts:
        attempts += 1
        variant = expand_spintax(template, rnd).strip()
        if not variant:
            continue
        if variant in seen:
            continue
        seen.add(variant)
        variants.append(variant)

    # If unique combinations are exhausted, fill remaining rows with random variants.
    while len(variants) < count:
        variant = expand_spintax(template, rnd).strip()
        if variant:
            variants.append(variant)

    return variants
