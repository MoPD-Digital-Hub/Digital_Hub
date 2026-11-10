import os
from urllib.parse import urlparse


def _is_valid_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def validate_ai_config(debug: bool):
    errors = []

    vllm_base = os.getenv("VLLM_API_BASE", "")
    embed_base = os.getenv("EMBEDDING_API_BASE", "")

    if vllm_base and not _is_valid_url(vllm_base):
        errors.append("VLLM_API_BASE must be a valid URL")

    if embed_base and not _is_valid_url(embed_base):
        errors.append("EMBEDDING_API_BASE must be a valid URL")

    if not debug and not vllm_base:
        errors.append("VLLM_API_BASE is required in production")
    if not debug and not embed_base:
        errors.append("EMBEDDING_API_BASE is required in production")

    if errors:
        raise ValueError("; ".join(errors))
