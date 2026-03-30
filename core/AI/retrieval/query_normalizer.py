import logging

from AI.gemini.client import GeminiClientError, GeminiTextClient
from AI.gemini.language import detect_language

LOGGER = logging.getLogger("AI.retrieval.query_normalizer")

RETRIEVAL_SYSTEM_PROMPT = """
Convert the user's retrieval query into concise English for semantic search.

Rules:
- Preserve indicator codes exactly.
- Preserve ministry, topic, category, and policy names.
- Preserve years, quarters, and dates exactly.
- Keep the meaning of the query.
- Return only the normalized English retrieval query.
"""


def normalize_retrieval_query(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return ""
    if detect_language(text) != "Amharic":
        return text

    client = GeminiTextClient()
    try:
        result = client.generate_text(
            prompt=text,
            system_instruction=RETRIEVAL_SYSTEM_PROMPT,
            temperature=0,
        )
        normalized = str(result or "").strip()
        return normalized or text
    except GeminiClientError:
        LOGGER.warning("Falling back to original Amharic query for retrieval normalization.")
        return text
