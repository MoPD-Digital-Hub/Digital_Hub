import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str
    model: str
    timeout_seconds: int
    temperature: float
    top_p: float
    max_output_tokens: int
    max_history_questions: int
    stream_chunk_chars: int


def get_gemini_settings() -> GeminiSettings:
    return GeminiSettings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        timeout_seconds=int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30")),
        temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
        top_p=float(os.getenv("GEMINI_TOP_P", "0.9")),
        max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048")),
        max_history_questions=int(os.getenv("MAX_HISTORY_QUESTIONS", os.getenv("GEMINI_HISTORY_TURNS", "4"))),
        stream_chunk_chars=int(os.getenv("GEMINI_STREAM_CHUNK_CHARS", "180")),
    )


def validate_gemini_settings(debug: bool):
    settings = get_gemini_settings()
    errors = []

    if not debug and not settings.api_key:
        errors.append("GEMINI_API_KEY is required in production")
    if settings.timeout_seconds <= 0:
        errors.append("GEMINI_TIMEOUT_SECONDS must be greater than 0")
    if not 0 <= settings.temperature <= 2:
        errors.append("GEMINI_TEMPERATURE must be between 0 and 2")
    if not 0 < settings.top_p <= 1:
        errors.append("GEMINI_TOP_P must be between 0 and 1")
    if settings.max_output_tokens <= 0:
        errors.append("GEMINI_MAX_OUTPUT_TOKENS must be greater than 0")
    if settings.max_history_questions < 0:
        errors.append("MAX_HISTORY_QUESTIONS must be 0 or greater")
    if settings.stream_chunk_chars <= 0:
        errors.append("GEMINI_STREAM_CHUNK_CHARS must be greater than 0")

    if errors:
        raise ValueError("; ".join(errors))
