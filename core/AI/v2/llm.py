"""Calls to the Ministry LLM gateway (OpenAI-compatible vLLM).

The gateway does not enable native tool calling, but honours
response_format=json_schema, so planning uses structured output.
"""

import asyncio
import json
import os
import weakref

import numpy as np
from openai import AsyncOpenAI

from AI.infrastructure.providers import _normalize_openai_base_url, get_streaming_client_config


class LLMError(Exception):
    pass


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
        config = get_streaming_client_config()
        client = AsyncOpenAI(base_url=config["base_url"], api_key=config["api_key"],
                             timeout=config["timeout"], max_retries=config["max_retries"])
        _chat_clients[loop] = client
    return client


def _embed_client():
    loop = asyncio.get_running_loop()
    client = _embed_clients.get(loop)
    if client is None:
        default = "https://llm.mopd.gov.et/v1"
        client = AsyncOpenAI(
            base_url=_normalize_openai_base_url(os.getenv("EMBEDDING_API_BASE", default), fallback=default),
            api_key=os.getenv("EMBEDDING_API_KEY") or "EMPTY",
            timeout=int(os.getenv("AI_REQUEST_TIMEOUT", "60")),
            max_retries=int(os.getenv("AI_MAX_RETRIES", "3")),
        )
        _embed_clients[loop] = client
    return client


async def json_completion(messages, schema, *, name="output", max_tokens=600, temperature=0):
    """A completion constrained to `schema`, parsed into a dict."""
    config = get_streaming_client_config()
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


async def stream_completion(messages, *, max_tokens=1200, temperature=0.2):
    """Yield text pieces of a streamed completion."""
    config = get_streaming_client_config()
    try:
        stream = await _client().chat.completions.create(
            model=config["model"],
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                yield delta
    except Exception as exc:
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
    from AI.infrastructure.providers import get_remote_embeddings

    embeddings = get_remote_embeddings()
    if embeddings is None:
        raise LLMError("The embeddings client could not be created (check EMBEDDING_API_BASE / EMBEDDING_API_KEY).")
    vectors = np.asarray(embeddings.embed_documents(list(texts)), dtype=np.float32)
    return normalise(vectors)


def normalise(vectors):
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms
