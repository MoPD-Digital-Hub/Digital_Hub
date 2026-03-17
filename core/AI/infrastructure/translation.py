import os
import re

import requests

from AI.infrastructure.text_utils import compact_text, split_text_into_chunks

GEMINI_TEXT_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
AMHARIC_SCRIPT_PATTERN = re.compile(r"[\u1200-\u137F]")


def detect_request_language(text: str) -> str:
    return "Amharic" if AMHARIC_SCRIPT_PATTERN.search(str(text or "")) else "English"


def normalize_question_for_retrieval(question: str) -> tuple[str, str]:
    language = detect_request_language(question)
    if language == "Amharic":
        return translate_text_with_gemini(question, "English"), language
    return str(question or "").strip(), language


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        parts = ((candidate.get("content") or {}).get("parts")) or []
        for part in parts:
            text_value = str(part.get("text", "")).strip()
            if text_value:
                return text_value
    return ""


def _generate_gemini_text(prompt: str, *, model: str, system_instruction: str | None = None, temperature: float = 0.2) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    response = requests.post(
        GEMINI_TEXT_API_URL.format(model=model),
        params={"key": api_key},
        json={
            "system_instruction": {
                "parts": [{"text": system_instruction or ""}]
            } if system_instruction else None,
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            },
        },
        timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
    )
    response.raise_for_status()
    text = _extract_gemini_text(response.json())
    if not text:
        raise RuntimeError("Gemini did not return text.")
    return text


def translate_text_with_gemini(text: str, target_language: str = "Amharic") -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    source_text = compact_text(text)
    if not source_text:
        raise ValueError("Text is required for translation.")

    model = os.getenv("GEMINI_TRANSLATE_MODEL", "gemini-2.5-flash-lite").strip() or "gemini-2.5-flash-lite"
    translated_chunks = []
    for chunk in split_text_into_chunks(source_text, limit=1400):
        prompt = (
            "Translate the following assistant response into clear, professional {language}. "
            "Preserve all numeric analysis, percentages, dates, trend language, comparisons, rankings, and conclusions. "
            "If the source mentions increase, decrease, growth, decline, stability, highest, lowest, above average, below average, change over time, or period-to-period movement, keep that trend information explicitly in the translation. "
            "If the source gives a result plus an interpretation, keep both the result and the interpretation. "
            "Do not simplify the response into a definition only. "
            "Keep the analytical meaning intact and keep all numbers exactly as written. "
            "Return only the translated text with no explanation, no headings, and no markdown.\n\n"
            "{text}"
        ).format(language=target_language, text=chunk)

        chunk_text = _generate_gemini_text(prompt, model=model, temperature=0.2)
        if not chunk_text:
            raise RuntimeError("Gemini translation did not return text.")
        translated_chunks.append(chunk_text)

    return "\n\n".join(translated_chunks).strip()


def generate_answer_with_gemini(
    *,
    context: str,
    question: str,
    system_rule: str,
    target_language: str = "Amharic",
) -> str:
    model = os.getenv("GEMINI_ANSWER_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    context_text = compact_text(context)[:14000]
    question_text = compact_text(question)
    prompt = (
        "Answer the user's DPMES question using the provided context.\n"
        "Output language: {language}\n"
        "Rules:\n"
        "- Use the context as the source of truth.\n"
        "- Keep all numbers, percentages, dates, ranks, and comparisons exactly correct.\n"
        "- If the context is insufficient, say so clearly.\n"
        "- Respond only in {language}.\n"
        "- Follow the HTML output style required by the system instruction.\n\n"
        "Context:\n{context}\n\n"
        "User question:\n{question}"
    ).format(language=target_language, context=context_text, question=question_text)
    return _generate_gemini_text(prompt, model=model, system_instruction=system_rule, temperature=0.15)
