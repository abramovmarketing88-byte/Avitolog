import random
import re


_SPINTAX_PATTERN = re.compile(r"\{([^{}]+)\}")


def expand_spintax(template: str) -> str:
    value = template or ""
    # Expand from inner groups to outer groups.
    while True:
        match = _SPINTAX_PATTERN.search(value)
        if not match:
            break
        options = [opt.strip() for opt in match.group(1).split("|") if opt.strip()]
        replacement = random.choice(options) if options else ""
        value = value[: match.start()] + replacement + value[match.end() :]
    return value
