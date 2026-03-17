import asyncio
import logging
import os
import re

from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema
from langchain_milvus import Milvus
from AI.parsing import YEAR_PATTERN, metadata_all_aliases, question_entity_aliases
from .constants import COLLECTION_NAME, DEFAULT_MILVUS_URI, INDICATOR_CODE_PATTERN
from .providers import get_remote_embeddings
_milvus_uri_in_use = None
LOGGER = logging.getLogger("AI.vectorstore")


def _normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _normalize_token(value):
    return re.sub(r"[^a-z0-9]+", "", _normalize_text(value))


def _extract_query_hints(question: str) -> dict:
    text = _normalize_text(question)
    year_match = YEAR_PATTERN.search(text)
    quarter = None
    if re.search(r"\b(q1|1st quarter|first quarter|3 month|3month)\b", text):
        quarter = "3month"
    elif re.search(r"\b(q2|2nd quarter|second quarter|6 month|6month|half year|semi[- ]?annual)\b", text):
        quarter = "6month"
    elif re.search(r"\b(q3|3rd quarter|third quarter|9 month|9month)\b", text):
        quarter = "9month"
    elif re.search(r"\b(q4|4th quarter|fourth quarter|12 month|12month|annual|full year)\b", text):
        quarter = "12month"

    indicator_codes = {match.group(0).lower() for match in INDICATOR_CODE_PATTERN.finditer(question or "")}
    query_tokens = {token for token in re.findall(r"[a-z0-9]+", text) if len(token) > 2}
    entity_aliases = question_entity_aliases(question or "")

    return {
        "text": text,
        "year": year_match.group(0) if year_match else None,
        "quarter": quarter,
        "indicator_codes": indicator_codes,
        "entity_aliases": entity_aliases,
        "tokens": query_tokens,
    }


def _metadata_relevance_score(doc, hints: dict) -> int:
    meta = getattr(doc, "metadata", {}) or {}
    score = 0

    indicator_code = _normalize_text(meta.get("indicator_code"))
    if indicator_code and indicator_code in hints["indicator_codes"]:
        score += 10

    metadata_aliases = metadata_all_aliases(meta)
    matched_aliases = metadata_aliases & hints["entity_aliases"]
    if matched_aliases:
        score += 9
        if any(len(alias) <= 6 for alias in matched_aliases):
            score += 2

    if hints["year"]:
        for key in ("year", "reference_year", "reporting_year"):
            if str(meta.get(key) or "").strip() == hints["year"]:
                score += 4
                break

    if hints["quarter"]:
        for key in ("quarter", "reporting_period", "period"):
            if _normalize_text(meta.get(key)) == hints["quarter"]:
                score += 3
                break

    for key in ("topic_name", "category_name", "indicator_eng", "responsible_ministry_eng"):
        value = _normalize_text(meta.get(key))
        if not value:
            continue
        matched_tokens = [token for token in hints["tokens"] if token in value]
        score += min(len(matched_tokens), 3)

    return score


def _deduplicate_docs(docs):
    deduped = []
    seen = set()
    for doc in docs or []:
        meta = getattr(doc, "metadata", {}) or {}
        key = (
            meta.get("pk")
            or meta.get("source_id")
            or meta.get("indicator_code"),
            meta.get("responsible_ministry_id"),
            getattr(doc, "page_content", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped


def _search_kwargs_for_question(question: str) -> dict:
    hints = _extract_query_hints(question)
    k = 5
    fetch_k = 12
    lambda_mult = 0.4

    if hints["indicator_codes"] or hints["entity_aliases"]:
        fetch_k = 16
        lambda_mult = 0.25
    elif hints["year"] or hints["quarter"]:
        fetch_k = 14
        lambda_mult = 0.35

    return {"k": k, "fetch_k": fetch_k, "lambda_mult": lambda_mult}


def retrieve_documents(question: str):
    vs = get_vector_store()
    hints = _extract_query_hints(question)
    search_kwargs = _search_kwargs_for_question(question)
    try:
        docs = vs.max_marginal_relevance_search(
            question,
            k=search_kwargs["k"],
            fetch_k=search_kwargs["fetch_k"],
            lambda_mult=search_kwargs["lambda_mult"],
        )
    except Exception as exc:
        LOGGER.warning("MMR retrieval failed, falling back to similarity search: %s", str(exc))
        docs = vs.similarity_search(question, k=search_kwargs["fetch_k"])

    docs = _deduplicate_docs(docs)
    scored = sorted(
        docs,
        key=lambda doc: (_metadata_relevance_score(doc, hints), len(getattr(doc, "page_content", ""))),
        reverse=True,
    )
    return scored[: search_kwargs["k"]]


class QueryAwareRetriever:
    def invoke(self, question):
        return retrieve_documents(question)


def _candidate_milvus_uris():
    configured = os.getenv("MILVUS_URI", DEFAULT_MILVUS_URI).strip()
    candidates = [configured]
    if configured != DEFAULT_MILVUS_URI:
        candidates.append(DEFAULT_MILVUS_URI)
    # Keep order while removing duplicates.
    seen = set()
    ordered = []
    for uri in candidates:
        if uri and uri not in seen:
            seen.add(uri)
            ordered.append(uri)
    return ordered

def ensure_collection():
    global _milvus_uri_in_use

    last_error = None
    for uri in _candidate_milvus_uris():
        try:
            client = MilvusClient(uri=uri)
            
            if not client.has_collection(collection_name=COLLECTION_NAME):
                print(f"📦 Creating collection: {COLLECTION_NAME}")
                
                fields = [
        
                    FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
                ]
                schema = CollectionSchema(fields, description="Admas docs", enable_dynamic_field=True)
                
                client.create_collection(collection_name=COLLECTION_NAME, schema=schema)
            
            _milvus_uri_in_use = uri
            print(f"📦 Milvus Schema Connected! ({uri})")
            return client
        except Exception as e:
            last_error = e
            continue

    print(f"⚠️ Milvus Schema Check Failed: {last_error}")
    _milvus_uri_in_use = None
    return None
    

_vector_store = None  

def get_vector_store():
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    client = ensure_collection()
    if client is None:
        raise ConnectionError("⚠️ Milvus server is unavailable. Check MILVUS_URI or start local Milvus.")
    embeddings = get_remote_embeddings()

    if not embeddings:
        raise ConnectionError("⚠️ Embedding provider failed to initialize.")
    
    _vector_store = Milvus(
        embedding_function=embeddings,
        connection_args={
            "uri": _milvus_uri_in_use or os.getenv("MILVUS_URI", DEFAULT_MILVUS_URI),
            "alias": "default", 
        },
        collection_name=COLLECTION_NAME,
        text_field="text",
        vector_field="vector",
        primary_field="pk",
        enable_dynamic_field=True,
        auto_id=False,
    )
    return _vector_store

def get_retriever():
    get_vector_store()
    return QueryAwareRetriever()
