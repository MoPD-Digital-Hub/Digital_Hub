import re


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u1200-\u137F]+")

PHRASE_EXPANSIONS = {
    "gdp": "gross domestic product gdp",
    "cpi": "consumer price index cpi inflation",
    "inflation": "inflation consumer price index cpi",
    "export": "export exports export value",
    "coffee export": "coffee export coffee exports export value",
    "import": "import imports import value",
    "agriculture": "agriculture agricultural",
    "industry": "industry industrial",
    "health": "health",
    "education": "education",
    "employment": "employment labor labour",
    "unemployment": "unemployment labour labor employment",
    "poverty": "poverty",
    "population": "population demographic",
    "revenue": "revenue government revenue",
    "expenditure": "expenditure government expenditure spending",
    "foreign direct investment": "foreign direct investment fdi",
    "fdi": "foreign direct investment fdi",
    "exchange rate": "exchange rate forex",
    "balance of trade": "balance of trade trade balance",
    "agricultural gdp": "agriculture gross domestic product agricultural gdp",
    "agriculture contribution": "agriculture contribution share gross domestic product",
    "coffee": "coffee",
}

MINISTRY_ALIASES = {
    "moh": "ministry of health health",
    "moe": "ministry of education education",
    "mof": "ministry of finance finance",
    "mols": "ministry of labor and skills labour employment skills",
    "moi": "ministry of industry industry",
    "moa": "ministry of agriculture agriculture",
}


def resolve_indicator_query(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return ""

    resolved = f" {text.lower()} "

    for alias, expansion in MINISTRY_ALIASES.items():
        resolved = resolved.replace(f" {alias} ", f" {expansion} ")

    for phrase, expansion in sorted(PHRASE_EXPANSIONS.items(), key=lambda item: len(item[0]), reverse=True):
        resolved = resolved.replace(f" {phrase} ", f" {expansion} ")

    return re.sub(r"\s+", " ", resolved).strip()


def query_tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(str(text or "").lower()) if len(token) > 1}
