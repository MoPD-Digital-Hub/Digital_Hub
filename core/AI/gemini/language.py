import re

AMHARIC_PATTERN = re.compile(r"[\u1200-\u137F]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return "English"

    amharic_chars = len(AMHARIC_PATTERN.findall(value))
    latin_chars = len(LATIN_PATTERN.findall(value))

    if amharic_chars == 0 and latin_chars == 0:
        return "English"
    if amharic_chars >= latin_chars:
        return "Amharic"
    return "English"
