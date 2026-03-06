import os 
import asyncio
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema
from langchain_milvus import Milvus
from .providers import get_remote_embeddings

COLLECTION_NAME = "admas_data"
DEFAULT_MILVUS_URI = "http://localhost:19530"
_milvus_uri_in_use = None


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
    vs = get_vector_store()
    return vs.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5},
    )
