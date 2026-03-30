import logging
import re
import json
import ssl

import aiohttp
import certifi
import requests

from .config import get_gemini_settings

LOGGER = logging.getLogger("AI.gemini.client")
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class GeminiClientError(Exception):
    pass


class GeminiTextClient:
    def __init__(self, settings=None):
        self.settings = settings or get_gemini_settings()

    def generate(self, messages):
        if not self.settings.api_key:
            raise GeminiClientError("Gemini API key is not configured.")

        payload = self._build_payload(messages)
        try:
            response = requests.post(
                GEMINI_GENERATE_URL.format(model=self.settings.model),
                params={"key": self.settings.api_key},
                json=payload,
                timeout=self.settings.timeout_seconds,
                verify=certifi.where(),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.exception("Gemini request failed")
            raise GeminiClientError(str(exc)) from exc

        data = response.json()
        text = self._extract_text(data)
        if not text:
            raise GeminiClientError("Gemini returned an empty response.")
        return {
            "text": text,
            "usage": self._extract_usage(data),
        }

    def generate_text(self, *, prompt: str, system_instruction: str | None = None, temperature: float | None = None, model: str | None = None):
        if not self.settings.api_key:
            raise GeminiClientError("Gemini API key is not configured.")

        payload = {
            "contents": [{"role": "user", "parts": [{"text": str(prompt or "").strip()}]}],
            "generationConfig": {
                "temperature": self.settings.temperature if temperature is None else temperature,
                "topP": self.settings.top_p,
                "maxOutputTokens": self.settings.max_output_tokens,
            },
        }
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        try:
            response = requests.post(
                GEMINI_GENERATE_URL.format(model=model or self.settings.model),
                params={"key": self.settings.api_key},
                json=payload,
                timeout=self.settings.timeout_seconds,
                verify=certifi.where(),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.exception("Gemini text request failed")
            raise GeminiClientError(str(exc)) from exc

        data = response.json()
        text = self._extract_text(data)
        if not text:
            raise GeminiClientError("Gemini returned an empty response.")
        return text

    async def stream_generate(self, messages):
        if not self.settings.api_key:
            raise GeminiClientError("Gemini API key is not configured.")

        payload = self._build_payload(messages)
        url = GEMINI_GENERATE_URL.format(model=self.settings.model).replace(":generateContent", ":streamGenerateContent")

        try:
            timeout = aiohttp.ClientTimeout(total=self.settings.timeout_seconds)
            connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.post(
                    url,
                    params={"alt": "sse"},
                    json=payload,
                    headers={
                        "x-goog-api-key": self.settings.api_key,
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status >= 400:
                        detail = await response.text()
                        raise GeminiClientError(detail or f"Gemini streaming failed with status {response.status}.")

                    async for raw_line in response.content:
                        line = raw_line.decode("utf-8", errors="ignore").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = self._parse_sse_payload(line[5:].strip())
                        if not data:
                            continue
                        text = self._extract_text(data)
                        if text:
                            yield {
                                "text": text,
                                "usage": self._extract_usage(data),
                            }
        except aiohttp.ClientError as exc:
            LOGGER.exception("Gemini streaming request failed")
            raise GeminiClientError(str(exc)) from exc

    def iter_chunks(self, text: str):
        chunk_size = self.settings.stream_chunk_chars
        normalized = str(text or "").strip()
        if not normalized:
            return

        buffer = ""
        for sentence in re.split(r"(?<=[.!?።])\s+", normalized):
            sentence = sentence.strip()
            if not sentence:
                continue
            if buffer and len(buffer) + len(sentence) + 1 > chunk_size:
                yield buffer
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()

        if buffer:
            yield buffer

    def _build_payload(self, messages):
        normalized_messages = self._normalize_messages(messages)
        system_parts = [m["content"] for m in normalized_messages if m["role"] == "system"]
        contents = []
        for message in normalized_messages:
            if message["role"] == "system":
                continue
            role = "model" if message["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message["content"]}]})

        payload = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": {
                "temperature": self.settings.temperature,
                "topP": self.settings.top_p,
                "maxOutputTokens": self.settings.max_output_tokens,
            },
        }
        if system_parts:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    def _normalize_messages(self, messages):
        normalized = []
        for message in messages or []:
            role = str(message.get("role") or "user").strip().lower()
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if role not in {"system", "user", "assistant"}:
                role = "user"
            normalized.append({"role": role, "content": content})
        return normalized

    def _extract_text(self, payload):
        parts = []
        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                value = str(part.get("text") or "").strip()
                if value:
                    parts.append(value)
        return "\n".join(parts).strip()

    def _extract_usage(self, payload):
        metadata = payload.get("usageMetadata") or {}
        return {
            "prompt_tokens": metadata.get("promptTokenCount"),
            "completion_tokens": metadata.get("candidatesTokenCount"),
            "total_tokens": metadata.get("totalTokenCount"),
        }

    def _parse_sse_payload(self, raw_payload: str):
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
