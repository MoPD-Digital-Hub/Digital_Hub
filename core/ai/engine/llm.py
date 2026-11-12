"""Calls to the Ministry LLM gateway (OpenAI-compatible vLLM).

The gateway does not enable native tool calling, but honours
response_format=json_schema, so planning uses structured output.
"""

import asyncio
import json
import logging
import os
import weakref
from urllib.parse import urlparse

import numpy as np
from openai import AsyncOpenAI, OpenAI

DEFAULT_GATEWAY = "https://llm.mopd.gov.et/v1"

LOGGER = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def _base_url(url):
    """The /v1 base of an OpenAI-compatible URL; full endpoint URLs are accepted."""
    url = (url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/embeddings"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    if url and not url.endswith("/v1"):
        url += "/v1"
    parsed = urlparse(url)
    return url if parsed.scheme and parsed.netloc else DEFAULT_GATEWAY


def chat_config():
    return {
        "base_url": _base_url(os.getenv("VLLM_API_BASE", DEFAULT_GATEWAY)),
        "model": os.getenv("VLLM_MODEL", "gemma-4-31b"),
        "api_key": os.getenv("VLLM_API_KEY") or "EMPTY",
        "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
        "max_retries": int(os.getenv("AI_MAX_RETRIES", "3")),
    }


def embedding_config():
    return {
        "base_url": _base_url(os.getenv("EMBEDDING_API_BASE", DEFAULT_GATEWAY)),
        "api_key": os.getenv("EMBEDDING_API_KEY") or "EMPTY",
        "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
        "max_retries": int(os.getenv("AI_MAX_RETRIES", "3")),
    }


# One client per event loop: an async HTTP connection pool belongs to the loop
# that opened it. Daphne runs a single loop, but async_to_sync (REST, commands,
# tests) starts a new loop per call, and a shared client then fails with
# "Event loop is closed".
_chat_clients = weakref.WeakKeyDictionary()
_embed_clients = weakref.WeakKeyDictionary()


def _client():
    loop = asyncio.get_running_loop()
    client = _chat_clients.get(loop)
    if client is None:
        config = chat_config()
        client = AsyncOpenAI(base_url=config["base_url"], api_key=config["api_key"],
                             timeout=config["timeout"], max_retries=config["max_retries"])
        _chat_clients[loop] = client
    return client


def _embed_client():
    loop = asyncio.get_running_loop()
    client = _embed_clients.get(loop)
    if client is None:
        client = AsyncOpenAI(**embedding_config())
        _embed_clients[loop] = client
    return client


async def json_completion(messages, schema, *, name="output", max_tokens=600, temperature=0):
    """A completion constrained to `schema`, parsed into a dict."""
    config = chat_config()
    try:
        response = await _client().chat.completions.create(
            model=config["model"],
            messages=messages,
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return json.loads(response.choices[0].message.content or "{}")
    except (ValueError, IndexError) as exc:
        raise LLMError(f"The model returned an unreadable plan: {exc}") from exc
    except Exception as exc:  # network, auth, server errors from the SDK
        raise LLMError(f"The LLM gateway failed: {exc}") from exc


async def stream_completion(messages, *, max_tokens=1200, temperature=0.2, allowed_pattern=None):
    """Yield text pieces of a streamed completion.

    `allowed_pattern` (a regular expression) restricts what the model may
    generate, through vLLM's structured outputs (amharic.ALLOWED_PATTERN keeps
    Amharic answers to Ethiopic, Latin and punctuation). If the gateway rejects
    it before writing anything, the answer is written without it.
    """
    config = chat_config()
    extra = {"structured_outputs": {"regex": allowed_pattern}} if allowed_pattern else None
    started = False
    try:
        stream = await _client().chat.completions.create(
            model=config["model"],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            extra_body=extra,
        )
        async for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                started = True
                yield delta
    except Exception as exc:
        if allowed_pattern and not started:
            LOGGER.warning("The gateway rejected the character restriction; writing without it: %s", exc)
            async for piece in stream_completion(messages, max_tokens=max_tokens, temperature=temperature):
                yield piece
            return
        raise LLMError(f"The LLM gateway failed while writing the answer: {exc}") from exc


def embedding_model():
    return os.getenv("EMBEDDING_MODEL", "bge-m3")


async def embed_query(text):
    """One normalised vector for a short query."""
    try:
        response = await _embed_client().embeddings.create(model=embedding_model(), input=[text])
    except Exception as exc:
        raise LLMError(f"The embeddings gateway failed: {exc}") from exc
    return normalise(np.asarray(response.data[0].embedding, dtype=np.float32))


def embed_documents(texts):
    """Normalised vectors for many texts (used by the catalog sync)."""
    try:
        response = OpenAI(**embedding_config()).embeddings.create(model=embedding_model(), input=list(texts))
    except Exception as exc:
        raise LLMError(f"The embeddings gateway failed: {exc}") from exc
    vectors = np.asarray([item.embedding for item in sorted(response.data, key=lambda d: d.index)], dtype=np.float32)
    return normalise(vectors)


def normalise(vectors):
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms
