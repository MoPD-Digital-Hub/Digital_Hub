import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalSettings:
    milvus_uri: str
    collection_name: str
    embedding_api_base: str
    embedding_model: str
    embedding_api_key: str
    time_series_api_base: str
    time_series_indicator_limit: int
    retrieval_k: int
    retrieval_fetch_k: int
    retrieval_timeout_seconds: int
    dpmes_api_base: str = "https://dpmes.mopd.gov.et"
    public_body_score_limit: int = 1


def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings(
        milvus_uri=os.getenv("MILVUS_URI", "http://localhost:19530").strip(),
        collection_name=os.getenv("MILVUS_COLLECTION_NAME", "admas_data").strip() or "admas_data",
        embedding_api_base=os.getenv("EMBEDDING_API_BASE", "").strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5").strip() or "BAAI/bge-base-en-v1.5",
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", "empty").strip() or "empty",
        time_series_api_base=os.getenv("TIME_SERIES_API_BASE", "https://time-series.mopd.gov.et/api/mobile").strip(),
        time_series_indicator_limit=int(os.getenv("TIME_SERIES_INDICATOR_LIMIT", "1")),
        retrieval_k=int(os.getenv("MILVUS_RETRIEVAL_K", "5")),
        retrieval_fetch_k=int(os.getenv("MILVUS_RETRIEVAL_FETCH_K", "12")),
        retrieval_timeout_seconds=int(os.getenv("MILVUS_TIMEOUT_SECONDS", "30")),
        dpmes_api_base=os.getenv("DPMES_API_BASE", "https://dpmes.mopd.gov.et").strip() or "https://dpmes.mopd.gov.et",
        public_body_score_limit=int(os.getenv("PUBLIC_BODY_SCORE_LIMIT", "1")),
    )


def validate_retrieval_settings(debug: bool):
    settings = get_retrieval_settings()
    errors = []

    if not debug and not settings.milvus_uri:
        errors.append("MILVUS_URI is required in production")
    if not debug and not settings.embedding_api_base:
        errors.append("EMBEDDING_API_BASE is required in production")
    if not debug and not settings.time_series_api_base:
        errors.append("TIME_SERIES_API_BASE is required in production")
    if settings.retrieval_k <= 0:
        errors.append("MILVUS_RETRIEVAL_K must be greater than 0")
    if settings.retrieval_fetch_k < settings.retrieval_k:
        errors.append("MILVUS_RETRIEVAL_FETCH_K must be greater than or equal to MILVUS_RETRIEVAL_K")
    if settings.retrieval_timeout_seconds <= 0:
        errors.append("MILVUS_TIMEOUT_SECONDS must be greater than 0")
    if settings.time_series_indicator_limit <= 0:
        errors.append("TIME_SERIES_INDICATOR_LIMIT must be greater than 0")
    if settings.public_body_score_limit <= 0:
        errors.append("PUBLIC_BODY_SCORE_LIMIT must be greater than 0")

    if errors:
        raise ValueError("; ".join(errors))
