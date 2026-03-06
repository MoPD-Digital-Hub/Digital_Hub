import os
import logging
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError

_llm_cache = None
_embeddings_cache = None
LOGGER = logging.getLogger(__name__)

def _normalize_openai_base_url(url: str, fallback: str) -> str:
    if not url:
        return fallback

    normalized = url.strip().rstrip("/")

    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    if normalized.endswith("/embeddings"):
        normalized = normalized[: -len("/embeddings")]

    # OpenAI-compatible providers typically expose /v1 base.
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return fallback

    return normalized

def get_llm_instance():
    """Returns the cached LLM instance or creates a new one."""
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache

    default_llm_url = "http://localhost:8000/v1"
    VLLM_URL = _normalize_openai_base_url(
        os.getenv("VLLM_API_BASE", default_llm_url),
        fallback=default_llm_url,
    )
    VLLM_MODEL = os.getenv("VLLM_MODEL", "openai/gpt-oss-20b")
    OPENAI_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
    REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "60"))
    MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

    try:
        _llm_cache = ChatOpenAI(
            openai_api_base=VLLM_URL,
            openai_api_key=OPENAI_API_KEY,
            model=VLLM_MODEL,
            streaming=True,
            temperature=0,
            request_timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES
        )
        return _llm_cache
    except (APIConnectionError, APITimeoutError) as e:
        LOGGER.error("Could not connect to vLLM server: %s", str(e))
    except Exception as e:
        LOGGER.exception("Unexpected error initializing LLM: %s", str(e))
    
    return None

def get_remote_embeddings():
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache

    default_embed_url = "http://196.189.61.160:4001/v1"
    EMBED_URL = _normalize_openai_base_url(
        os.getenv("EMBEDDING_API_BASE", default_embed_url),
        fallback=default_embed_url,
    )
    EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
    EMBED_API_KEY = os.getenv("EMBEDDING_API_KEY", "empty")
    REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "60"))

    try:
        _embeddings_cache = OpenAIEmbeddings(
            model=EMBED_MODEL,
            api_key=EMBED_API_KEY,
            base_url=EMBED_URL,
            timeout=REQUEST_TIMEOUT,
            tiktoken_enabled=False, 
            check_embedding_ctx_length=False
        )
        return _embeddings_cache
    except Exception as e:
        LOGGER.exception("Failed to initialize Remote Embeddings: %s", str(e))
    
    return None


def clear_provider_caches():
    global _llm_cache, _embeddings_cache
    _llm_cache = None
    _embeddings_cache = None
