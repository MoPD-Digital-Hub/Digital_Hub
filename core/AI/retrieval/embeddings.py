from urllib.parse import urlparse

from langchain_openai import OpenAIEmbeddings

from .config import get_retrieval_settings

_embeddings_cache = None


def _normalize_openai_base_url(url: str) -> str:
    normalized = str(url or "").strip().rstrip("/")
    if normalized.endswith("/embeddings"):
        normalized = normalized[: -len("/embeddings")]
    if normalized and not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("EMBEDDING_API_BASE must be a valid URL")
    return normalized


def get_embeddings():
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache

    settings = get_retrieval_settings()
    base_url = _normalize_openai_base_url(settings.embedding_api_base)
    _embeddings_cache = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=base_url,
        timeout=settings.retrieval_timeout_seconds,
        tiktoken_enabled=False,
        check_embedding_ctx_length=False,
    )
    return _embeddings_cache
