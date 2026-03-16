import os

import requests

from AI.infrastructure.text_utils import compact_text, split_text_into_chunks

GEMINI_TEXT_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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

        response = requests.post(
            GEMINI_TEXT_API_URL.format(model=model),
            params={"key": api_key},
            json={
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
                    "temperature": 0.2,
                },
            },
            timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
        )
        response.raise_for_status()

        payload = response.json()
        candidates = payload.get("candidates") or []
        chunk_text = ""
        for candidate in candidates:
            parts = ((candidate.get("content") or {}).get("parts")) or []
            for part in parts:
                text_value = str(part.get("text", "")).strip()
                if text_value:
                    chunk_text = text_value
                    break
            if chunk_text:
                break

        if not chunk_text:
            raise RuntimeError("Gemini translation did not return text.")
        translated_chunks.append(chunk_text)

    return "\n\n".join(translated_chunks).strip()
