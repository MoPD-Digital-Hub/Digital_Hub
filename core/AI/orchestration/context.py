import re
from dataclasses import dataclass, field

from .preprocessing import QueryPreprocessor


FILLER_PATTERN = re.compile(r"\b(?:generate|create|build|make|a|an|the|dashboard|about|for|on|please|now)\b", re.IGNORECASE)
PRONOUN_PATTERN = re.compile(r"^(it|that|this|them|those|these)$", re.IGNORECASE)


@dataclass
class ResolvedConversationIntent:
    primary_intent: str
    secondary_intents: list[str] = field(default_factory=list)
    resolved_prompt: str = ""
    topic: str = ""
    preprocessed: object | None = None
    follow_up_context: dict = field(default_factory=dict)
    context_dependent: bool = False
    return_existing_link: bool = False
    existing_dashboard: dict = field(default_factory=dict)


class ConversationStateResolver:
    LINK_REQUEST_TERMS = (
        "dashboard link",
        "show me the link",
        "where is the link",
        "where is the dashboard link",
        "return the link",
        "give me the link",
        "show the link",
        "link please",
        "የዳሽቦርድ ሊንክ",
        "ሊንኩን አሳየኝ",
        "ሊንኩን ስጠኝ",
    )

    DASHBOARD_FOLLOW_UP_TERMS = (
        "generate it",
        "create it",
        "build it",
        "make it",
        "generate it now",
        "create it now",
        "build it now",
        "make it now",
        "okay generate the dashboard",
        "now build it",
        "generate the dashboard",
        "create the dashboard",
        "build the dashboard",
        "make the dashboard",
        "ፍጠረው",
        "አዘጋጅ",
        "ዳሽቦርዱን ፍጠር",
        "አሁን ፍጠር",
    )
    CONTEXT_FOLLOW_UP_TERMS = (
        "give me detail analysis",
        "give me detailed analysis",
        "give me detail info",
        "give me detailed info",
        "detail info",
        "detailed info",
        "detail analysis",
        "detailed analysis",
        "explain more",
        "analyze it",
        "analyze it deeply",
        "analyze deeply",
        "show more",
        "what does this mean",
        "give more insight",
        "more insight",
        "elaborate",
        "more detail",
        "more details",
        "explain it",
        "explain this",
        "tell me more",
        "dig deeper",
        "give deeper analysis",
        "table format",
        "tabl format",
        "in table format",
        "as a table",
        "show as table",
        "show in table format",
        "give me the data in table format",
        "give me the data in tabl format",
        "ጥልቅ ትንተና",
        "ዝርዝር ትንተና",
        "በተጨማሪ አብራራ",
        "የበለጠ አብራራ",
        "ይህ ምን ማለት ነው",
        "ተጨማሪ ግንዛቤ",
    )

    def __init__(self, classifier, preprocessor=None):
        self.classifier = classifier
        self.preprocessor = preprocessor or QueryPreprocessor()

    def resolve(self, question: str, history_records=None) -> ResolvedConversationIntent:
        current = self.classifier.analyze(question)
        primary_intent = current["primary_intent"]
        secondary_intents = current["secondary_intents"]
        preprocessed = current.get("preprocessed") or self.preprocessor.preprocess(question)
        records = history_records or []
        latest_dashboard = self._latest_dashboard_state(records)
        latest_context = self._latest_context_state(records)
        recent_topic = self._latest_topic(records)
        text = str(preprocessed.best_query or question or "").strip()
        lowered = text.lower()

        if primary_intent == "dashboard_generation":
            topic = self._extract_topic(text)
            if self._is_placeholder_topic(topic):
                topic = latest_dashboard.get("topic") or recent_topic
            resolved_prompt = self._resolve_dashboard_prompt(text, topic)
            return ResolvedConversationIntent(
                primary_intent="dashboard_generation",
                secondary_intents=secondary_intents,
                resolved_prompt=resolved_prompt,
                topic=topic,
                preprocessed=preprocessed,
                follow_up_context=latest_context,
                existing_dashboard=latest_dashboard.get("dashboard") or {},
            )

        if latest_dashboard:
            if any(term in lowered for term in self.LINK_REQUEST_TERMS):
                return ResolvedConversationIntent(
                    primary_intent="dashboard_generation",
                    secondary_intents=["time_series_query"] if latest_dashboard.get("topic") else [],
                    resolved_prompt=latest_dashboard.get("resolved_prompt") or self._resolve_dashboard_prompt("", latest_dashboard.get("topic") or ""),
                    topic=latest_dashboard.get("topic") or "",
                    preprocessed=preprocessed,
                    follow_up_context=latest_context,
                    return_existing_link=True,
                    existing_dashboard=latest_dashboard.get("dashboard") or {},
                )
            if any(term in lowered for term in self.DASHBOARD_FOLLOW_UP_TERMS):
                return ResolvedConversationIntent(
                    primary_intent="dashboard_generation",
                    secondary_intents=["time_series_query"] if latest_dashboard.get("topic") else [],
                    resolved_prompt=latest_dashboard.get("resolved_prompt") or self._resolve_dashboard_prompt("", latest_dashboard.get("topic") or ""),
                    topic=latest_dashboard.get("topic") or "",
                    preprocessed=preprocessed,
                    follow_up_context=latest_context,
                    existing_dashboard=latest_dashboard.get("dashboard") or {},
                )

        if self._is_context_dependent_query(lowered) and latest_context:
            reconstructed_prompt = self._reconstruct_follow_up_query(text, latest_context)
            follow_up_preprocessed = self.preprocessor.preprocess(reconstructed_prompt)
            follow_up_analysis = self.classifier.analyze(reconstructed_prompt)
            previous_intent = latest_context.get("intent") or follow_up_analysis["primary_intent"]
            primary = "general_query" if previous_intent == "dashboard_generation" else previous_intent
            return ResolvedConversationIntent(
                primary_intent=primary,
                secondary_intents=follow_up_analysis.get("secondary_intents", []),
                resolved_prompt=reconstructed_prompt,
                topic=latest_context.get("topic") or recent_topic,
                preprocessed=follow_up_preprocessed,
                follow_up_context=latest_context,
                context_dependent=True,
                existing_dashboard=latest_dashboard.get("dashboard") or {},
            )

        return ResolvedConversationIntent(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            resolved_prompt=text,
            topic="",
            preprocessed=preprocessed,
            follow_up_context=latest_context,
        )

    def _latest_dashboard_state(self, history_records):
        for item in reversed(history_records or []):
            tool_data = dict(item.get("tool_data") or {})
            if tool_data.get("intent") == "dashboard_generation":
                return {
                    "topic": tool_data.get("topic") or self._extract_topic(item.get("question") or ""),
                    "resolved_prompt": tool_data.get("resolved_prompt") or "",
                    "dashboard": dict(tool_data.get("last_tool_result") or {}),
                }
            question = str(item.get("question") or "").strip()
            if self.classifier.analyze(question)["primary_intent"] == "dashboard_generation":
                return {
                    "topic": self._extract_topic(question),
                    "resolved_prompt": self._resolve_dashboard_prompt(question, self._extract_topic(question)),
                    "dashboard": {},
                }
        return {}

    def _latest_topic(self, history_records):
        for item in reversed(history_records or []):
            question = str(item.get("question") or "").strip()
            topic = self._extract_topic(question)
            if not self._is_placeholder_topic(topic):
                return topic
        return ""

    def _latest_context_state(self, history_records):
        for item in reversed(history_records or []):
            question = str(item.get("question") or "").strip()
            response = str(item.get("response") or "").strip()
            if not question:
                continue
            tool_data = dict(item.get("tool_data") or {})
            charts = list(item.get("chart_data") or [])
            analyzed = self.classifier.analyze(question)
            intent = tool_data.get("intent") or analyzed["primary_intent"]
            topic = tool_data.get("topic") or self._extract_topic(question)
            resolved_prompt = tool_data.get("resolved_prompt") or question
            if response or topic:
                return {
                    "intent": intent,
                    "topic": topic,
                    "question": question,
                    "response": response,
                    "resolved_prompt": resolved_prompt,
                    "tool_data": tool_data,
                    "charts": charts,
                }
        return {}

    def _extract_topic(self, question: str) -> str:
        text = str(question or "").strip()
        if not text:
            return ""
        cleaned = FILLER_PATTERN.sub(" ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        return cleaned

    def _resolve_dashboard_prompt(self, question: str, topic: str) -> str:
        text = str(question or "").strip()
        if text and "dashboard" in text.lower() and not self._is_placeholder_topic(self._extract_topic(text)):
            return text
        if topic:
            return f"generate a dashboard about {topic}"
        return text or "generate a dashboard"

    def _is_context_dependent_query(self, lowered_text: str) -> bool:
        text = str(lowered_text or "").strip()
        if not text:
            return False
        if any(term in text for term in self.CONTEXT_FOLLOW_UP_TERMS):
            return True
        return text in {
            "analyze",
            "analysis",
            "details",
            "detail",
            "detail info",
            "detailed info",
            "explain",
            "more",
            "insight",
            "meaning",
            "table",
            "table format",
        }

    def _reconstruct_follow_up_query(self, text: str, latest_context: dict) -> str:
        topic = str(latest_context.get("topic") or latest_context.get("resolved_prompt") or latest_context.get("question") or "").strip()
        previous_intent = latest_context.get("intent")
        lowered = str(text or "").strip().lower()
        if previous_intent == "dashboard_generation":
            if any(phrase in lowered for phrase in ("what does this mean", "meaning")):
                return f"What does the dashboard about {topic} mean?"
            if any(phrase in lowered for phrase in ("explain", "detail", "analysis", "insight", "more")):
                return f"Explain the dashboard about {topic} in more detail."
        if any(phrase in lowered for phrase in ("table", "tabl", "format")):
            return f"Show the data for {topic} in table format"
        if any(phrase in lowered for phrase in ("what does this mean", "meaning")):
            return f"What does {topic} mean?"
        if any(phrase in lowered for phrase in ("analysis", "analyze", "insight")):
            return f"Give me detailed analysis of {topic}"
        if any(phrase in lowered for phrase in ("detail info", "detailed info", "detail", "details")):
            return f"Give me detailed information about {topic}"
        if any(phrase in lowered for phrase in ("explain", "elaborate")):
            return f"Explain more about {topic}"
        if any(phrase in lowered for phrase in ("show more", "more detail", "more details", "tell me more")):
            return f"Show more detail about {topic}"
        return f"{text.rstrip('.')} about {topic}".strip()

    def _is_placeholder_topic(self, topic: str) -> bool:
        value = str(topic or "").strip().lower()
        if not value:
            return True
        if PRONOUN_PATTERN.match(value):
            return True
        return value in {"dashboard", "the dashboard"}
