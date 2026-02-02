import os 
import asyncio
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema
from langchain_milvus import Milvus
from .providers import get_remote_embeddings

COLLECTION_NAME = "admas_data"
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")

def ensure_collection():
    try:
        client = MilvusClient(uri=MILVUS_URI)
        
        if not client.has_collection(collection_name=COLLECTION_NAME):
            print(f"📦 Creating collection: {COLLECTION_NAME}")
            
            fields = [
    
                FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
            ]
            schema = CollectionSchema(fields, description="Admas docs", enable_dynamic_field=True)
            
            client.create_collection(collection_name=COLLECTION_NAME, schema=schema)
        
        print('📦 Milvus Schema Connected!')
        return client
    except Exception as e:
        print(f"⚠️ Milvus Schema Check Failed: {e}")
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

    ensure_collection()
    embeddings = get_remote_embeddings()

    if not embeddings:
        raise ConnectionError("⚠️ Embedding provider failed to initialize.")
    
    _vector_store = Milvus(
        embedding_function=embeddings,
        connection_args={
            "uri": MILVUS_URI,
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