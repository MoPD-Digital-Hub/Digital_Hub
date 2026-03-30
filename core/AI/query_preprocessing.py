import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches

from AI.gemini.language import detect_language


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u1200-\u137F]+")
ENGLISH_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,}$")
STOPWORDS = {
    "a",
    "about",
    "and",
    "build",
    "create",
    "dashboard",
    "for",
    "generate",
    "in",
    "is",
    "it",
    "make",
    "now",
    "of",
    "on",
    "or",
    "please",
    "show",
    "the",
    "to",
    "what",
}
DOMAIN_TERMS = {
    "agriculture",
    "amount",
    "annual",
    "build",
    "chart",
    "coffee",
    "compare",
    "comparison",
    "contribution",
    "cpi",
    "current",
    "dashboard",
    "data",
    "decrease",
    "decline",
    "ethiopia",
    "export",
    "exports",
    "generate",
    "gold",
    "gdp",
    "graph",
    "growth",
    "import",
    "imports",
    "increase",
    "indicator",
    "inflation",
    "latest",
    "monthly",
    "performance",
    "quarterly",
    "rate",
    "series",
    "share",
    "summary",
    "time",
    "timeline",
    "trend",
    "value",
    "yearly",
}
SEMANTIC_EXPANSIONS = {
    "inflation": [
        "consumer price inflation",
        "cpi trend",
    ],
    "coffee export": [
        "coffee export performance",
        "coffee export value Ethiopia",
    ],
    "gold export": [
        "gold export performance",
        "gold export value Ethiopia",
    ],
    "export": [
        "export performance",
        "export value Ethiopia",
    ],
    "gdp": [
        "gross domestic product",
        "economic growth trend",
    ],
    "agriculture": [
        "agriculture performance",
        "agricultural sector trend",
    ],
}


@dataclass
class PreprocessedQuery:
    original: str
    normalized: str
    corrected: str
    variants: list[str] = field(default_factory=list)
    best_query: str = ""
    language: str = "English"
    corrections: dict[str, str] = field(default_factory=dict)


class QueryPreprocessor:
    def preprocess(self, question: str) -> PreprocessedQuery:
        original = str(question or "").strip()
        normalized = re.sub(r"\s+", " ", original).strip()
        language = detect_language(normalized) if normalized else "English"
        if not normalized:
            return PreprocessedQuery(
                original=original,
                normalized=normalized,
                corrected=normalized,
                variants=[normalized] if normalized else [],
                best_query=normalized,
                language=language,
            )

        if language != "English":
            return PreprocessedQuery(
                original=original,
                normalized=normalized,
                corrected=normalized,
                variants=[normalized],
                best_query=normalized,
                language=language,
            )

        corrected, corrections = self._correct_english_text(normalized)
        variants = self._build_variants(normalized, corrected)
        best_query = self._select_best_query(normalized, variants)
        return PreprocessedQuery(
            original=original,
            normalized=normalized,
            corrected=corrected,
            variants=variants,
            best_query=best_query,
            language=language,
            corrections=corrections,
        )

    def _correct_english_text(self, text: str) -> tuple[str, dict[str, str]]:
        corrections = {}
        pieces = []
        for token in TOKEN_PATTERN.findall(text):
            if ENGLISH_TOKEN_PATTERN.match(token.lower()):
                corrected = self._correct_token(token.lower())
                if corrected != token.lower():
                    corrections[token.lower()] = corrected
                    pieces.append((token, corrected))
                else:
                    pieces.append((token, token))
            else:
                pieces.append((token, token))

        corrected = text
        for original, replacement in pieces:
            corrected = re.sub(rf"\b{re.escape(original)}\b", replacement, corrected, count=1)
        corrected = re.sub(r"\s+", " ", corrected).strip()
        return corrected, corrections

    def _correct_token(self, token: str) -> str:
        if token in STOPWORDS or token in DOMAIN_TERMS:
            return token
        if len(token) < 4:
            return token
        match = get_close_matches(token, list(DOMAIN_TERMS), n=1, cutoff=0.84)
        if not match:
            return token
        candidate = match[0]
        if abs(len(candidate) - len(token)) > 3:
            return token
        return candidate

    def _build_variants(self, original: str, corrected: str) -> list[str]:
        variants = []
        for value in (corrected, original):
            self._append_unique(variants, value)

        lowered = corrected.lower()
        for phrase, expansions in sorted(SEMANTIC_EXPANSIONS.items(), key=lambda item: len(item[0]), reverse=True):
            if phrase not in lowered:
                continue
            for expansion in expansions:
                if phrase == lowered:
                    candidate = expansion
                else:
                    candidate = re.sub(re.escape(phrase), expansion, lowered, count=1)
                self._append_unique(variants, candidate)
                if len(variants) >= 4:
                    break
            if len(variants) >= 4:
                break

        return variants[:4]

    def _select_best_query(self, original: str, variants: list[str]) -> str:
        if not variants:
            return str(original or "").strip()

        def score(candidate: str):
            ratio = SequenceMatcher(None, original.lower(), candidate.lower()).ratio()
            correction_bonus = 0.08 if candidate != original else 0
            semantic_bonus = 0.04 if len(candidate.split()) >= len(original.split()) else 0
            return ratio + correction_bonus + semantic_bonus

        return max(variants, key=score)

    def _append_unique(self, values: list[str], candidate: str):
        cleaned = re.sub(r"\s+", " ", str(candidate or "").strip())
        if cleaned and cleaned not in values:
            values.append(cleaned)
