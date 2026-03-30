import re

from .preprocessing import QueryPreprocessor


INDICATOR_CODE_PATTERN = re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+(?:\.\d+)*\b")
DASHBOARD_ACTION_PATTERNS = (
    re.compile(r"\b(generate|create|build|make)\b(?:\s+\w+){0,4}\s+\bdashboard\b", re.IGNORECASE),
    re.compile(r"\bdashboard\b.*\b(generate|create|build|make)\b", re.IGNORECASE),
    re.compile(r"(ዳሽቦርድ).*(ፍጠር|ፍጠሩ|ፍጠርልኝ|ስራ|ስራልኝ|አዘጋጅ|ፍጠርልኝ)", re.IGNORECASE),
)
VISUAL_ANALYTICS_PATTERNS = (
    re.compile(r"\b(show|give|want|need|create|make|build)\b(?:\s+\w+){0,4}\b(visual|visualize|visualise|visually|charts|chart|graphs|graph|analytics|insights|interactive view|report view|data exploration)\b", re.IGNORECASE),
    re.compile(r"\b(visual|visualize|visualise|visually|charts|chart|graphs|graph|analytics|insights|interactive view|report view|data exploration)\b(?:\s+\w+){0,5}\b(for|of|about)\b", re.IGNORECASE),
    re.compile(r"\b(show|give)\b(?:\s+\w+){0,4}\bvisual data\b", re.IGNORECASE),
)


class IntentClassifier:
    DASHBOARD_TERMS = ("dashboard", "ዳሽቦርድ")
    VISUAL_ANALYTICS_TERMS = (
        "visual data",
        "visualize",
        "visualise",
        "visually",
        "visual view",
        "charts",
        "chart",
        "graphs",
        "graph",
        "analytics view",
        "interactive view",
        "report view",
        "data exploration",
        "insights visually",
    )
    SCORECARD_ENTITY_TERMS = (
        "ministry",
        "public body",
        "public bodies",
        "mopd",
    )
    SCORECARD_ACTION_TERMS = (
        "performance",
        "score",
        "scorecard",
        "performance score",
        "performance scorecard",
    )
    SCORECARD_COMBINED_PATTERNS = (
        re.compile(r"\b(public body|public bodies|ministry|mopd)\b.*\b(performance|score|scorecard)\b", re.IGNORECASE),
        re.compile(r"\b(performance|score|scorecard)\b.*\b(public body|public bodies|ministry|mopd)\b", re.IGNORECASE),
    )

    TIME_SERIES_TERMS = (
        "time series",
        "trend",
        "over time",
        "export",
        "exports",
        "import",
        "imports",
        "inflation",
        "indicator",
        "annual",
        "yearly",
        "quarterly",
        "monthly",
        "latest value",
        "current value",
        "indicator code",
        "compare",
        "comparison",
        "change",
        "growth",
        "decline",
        "increase",
        "decrease",
        "rate",
        "value",
        "data",
        "series",
        "how much",
        "contribution",
        "share",
        "amount",
        "total",
        "chart",
        "graph",
        "plot",
        "timeline",
        "trajectory",
        "አዝማሚያ",
        "ግራፍ",
        "ቻርት",
        "ንፅፅር",
        "አነፃፀር",
        "ለውጥ",
        "እድገት",
        "ቅናሽ",
        "ጭማሪ",
        "ዓመታዊ",
        "ወርሃዊ",
        "ሩብ",
        "መረጃ",
        "ዋጋ",
        "እሴት",
        "ምን ያህል",
        "በጊዜ",
    )

    def __init__(self, preprocessor=None):
        self.preprocessor = preprocessor or QueryPreprocessor()

    def analyze(self, question: str) -> dict:
        preprocessed = self.preprocessor.preprocess(question)
        text = str(preprocessed.best_query or question or "").strip().lower()
        if not text:
            return {"primary_intent": "general_query", "secondary_intents": [], "preprocessed": preprocessed}

        has_dashboard_intent = self._has_explicit_dashboard_request(preprocessed)
        has_scorecard_intent = self._has_scorecard_intent(preprocessed)
        has_time_series_intent = self._has_time_series_intent(preprocessed)

        if has_dashboard_intent:
            secondary = ["time_series_query"] if has_time_series_intent else []
            return {"primary_intent": "dashboard_generation", "secondary_intents": secondary, "preprocessed": preprocessed}
        if has_scorecard_intent:
            return {"primary_intent": "scorecard_query", "secondary_intents": [], "preprocessed": preprocessed}
        if has_time_series_intent:
            return {"primary_intent": "time_series_query", "secondary_intents": [], "preprocessed": preprocessed}
        return {"primary_intent": "general_query", "secondary_intents": [], "preprocessed": preprocessed}

    def classify(self, question: str) -> str:
        return self.analyze(question)["primary_intent"]

    def _has_explicit_dashboard_request(self, preprocessed) -> bool:
        raw_text = str(preprocessed.best_query or preprocessed.corrected or preprocessed.normalized or "").strip()
        lowered = raw_text.lower()
        if any(term in lowered for term in self.DASHBOARD_TERMS):
            return any(pattern.search(raw_text) for pattern in DASHBOARD_ACTION_PATTERNS)
        if not any(term in lowered for term in self.VISUAL_ANALYTICS_TERMS):
            return False
        if any(pattern.search(raw_text) for pattern in VISUAL_ANALYTICS_PATTERNS):
            return True
        has_visual_request = any(term in lowered for term in ("visual", "chart", "graph", "analytics", "insight", "interactive view", "report view", "data exploration"))
        has_topic_reference = any(token in lowered for token in (" for ", " about ", " of ", " sector", " ministry", " public body", " productive"))
        return has_visual_request and has_topic_reference

    def _has_time_series_intent(self, preprocessed) -> bool:
        variants = [preprocessed.best_query, preprocessed.corrected, preprocessed.normalized] + list(preprocessed.variants or [])
        for value in variants:
            text = str(value or "").strip().lower()
            if not text:
                continue
            if INDICATOR_CODE_PATTERN.search(str(value or "").strip()):
                return True
            if any(term in text for term in self.TIME_SERIES_TERMS):
                return True
        return False

    def _has_scorecard_intent(self, preprocessed) -> bool:
        direct_inputs = [preprocessed.corrected, preprocessed.normalized, preprocessed.original]
        for value in direct_inputs:
            text = str(value or "").strip().lower()
            if not text:
                continue
            has_action = any(term in text for term in self.SCORECARD_ACTION_TERMS)
            has_entity = any(term in text for term in self.SCORECARD_ENTITY_TERMS)
            if "public body performance" in text or "public body score" in text or "public body scorecard" in text:
                return True
            if any(pattern.search(text) for pattern in self.SCORECARD_COMBINED_PATTERNS):
                return True
            if "mopd" in text and has_action:
                return True
            if has_entity and has_action:
                return True
        return False
