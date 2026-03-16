import base64
import io
import os
import re
import wave

import requests

from AI.infrastructure.text_utils import compact_text


GEMINI_TTS_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _compact_text(text: str, limit: int = 3500) -> str:
    return compact_text(text, limit=limit)


def _parse_sample_rate(mime_type: str, fallback: int = 24000) -> int:
    match = re.search(r"rate=(\d+)", str(mime_type or ""))
    if not match:
        return fallback
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return fallback


def _pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def synthesize_gemini_tts(
    text: str,
    voice_name: str | None = None,
    language_hint: str | None = None,
) -> tuple[bytes, str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    source_text = _compact_text(text)
    if not source_text:
        raise ValueError("Text is required for speech synthesis.")

    model = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts").strip()
    voice = (voice_name or os.getenv("GEMINI_TTS_VOICE", "Charon")).strip() or "Charon"
    language = str(language_hint or "English").strip() or "English"
    prompt = "Speak the following text naturally in {language}. Text: {text}".format(
        language=language,
        text=source_text,
    )

    response = requests.post(
        GEMINI_TTS_API_URL.format(model=model),
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
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice,
                        }
                    }
                },
            },
        },
        timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
    )
    response.raise_for_status()

    payload = response.json()
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        parts = ((candidate.get("content") or {}).get("parts")) or []
        for part in parts:
            inline = part.get("inlineData") or {}
            encoded_data = inline.get("data")
            mime_type = inline.get("mimeType") or "audio/L16;rate=24000"
            if not encoded_data:
                continue

            audio_bytes = base64.b64decode(encoded_data)
            if mime_type.lower().startswith("audio/l16"):
                sample_rate = _parse_sample_rate(mime_type)
                return _pcm_to_wav_bytes(audio_bytes, sample_rate), "audio/wav"
            return audio_bytes, mime_type

    raise RuntimeError("Gemini TTS did not return audio data.")
