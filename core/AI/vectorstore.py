import os 
from pymilvus import MilvusClient, DataType, FieldSchema, CollectionSchema
from langchain_milvus import Milvus
from .providers import get_remote_embeddings

COLLECTION_NAME = "admas_data"
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")

def ensure_collection():
    """
    Checks if the collection exists; if not, creates it with the proper schema.
    This replaces the 'naked' if-statements in your original file.
    """
    try:
        client = MilvusClient(uri=MILVUS_URI)
        
        if not client.has_collection(collection_name=COLLECTION_NAME):
            print(f"📦 Creating collection: {COLLECTION_NAME}")
            
            # Define Schema
            fields = [
                FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description="Admas docs", enable_dynamic_field=True)
            
            client.create_collection(collection_name=COLLECTION_NAME, schema=schema)
        
        return client
    except Exception as e:
        print(f"⚠️ Milvus Schema Check Failed: {e}")
        return None

def get_vector_store():
    """
    The main helper for LangChain. Call this whenever you need to 
    add documents or perform a search.
    """
    ensure_collection()

    embeddings = get_remote_embeddings()
    if not embeddings:
        raise ConnectionError("Could not initialize Embeddings. Check the AI server.")

    return Milvus(
        embedding_function=embeddings,
        connection_args={"uri": MILVUS_URI},
        collection_name=COLLECTION_NAME,
        text_field="text",
        vector_field="vector",
        primary_field="pk",
        metadata_field="metadata",
        auto_id=False,
        drop_old=False,
    )

def get_retriever():
    vs = get_vector_store()
    return vs.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5},
    )