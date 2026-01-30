import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from AI.utils import process_document
from .models import Document as doc
from langchain_milvus import Milvus
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import MilvusClient
from asgiref.sync import sync_to_async
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility


COLLECTION_NAME = "admas_data"

llm = ChatOpenAI(
    openai_api_base="http://localhost:8000/v1",
    openai_api_key="EMPTY",
    model="openai/gpt-oss-20b",
    streaming=False,
    temperature = 0.2,
    request_timeout=60
)


# 2️⃣ Initialize embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-en-v1.5",
    encode_kwargs={"normalize_embeddings": True}
)


# -----------------------------
# 5️⃣ Initialize LangChain Milvus vector store
# -----------------------------
client = MilvusClient("http://localhost:19530")


# for c in client.list_collections():
#     client.drop_collection(c)

# Updated Schema
fields = [
    FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
    FieldSchema(name="metadata", dtype=DataType.JSON),
]

schema = CollectionSchema(fields, description="Admas docs", enable_dynamic_field=True)

# Check if collection exists, create if not
if not client.has_collection(collection_name=COLLECTION_NAME):
    client.create_collection(collection_name=COLLECTION_NAME, schema=schema)



def get_vector_store():
    """
    Helper to initialize the Milvus connection.
    Calling this ensures the connection is ready when needed.
    """
    return Milvus(
        embedding_function=embeddings,
        connection_args={"uri": "http://localhost:19530"},
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

async def process_new_documents(text_splitter, _unused_vs):
    vs = get_vector_store()
    doc_data = await sync_to_async(lambda: list(doc.objects.filter(is_loaded=False)))()
    
    if len(doc_data) > 0:
        for document in doc_data:
            await process_document(document, vs)


# -----------------------------
# 6️⃣ Initialize text splitter
# -----------------------------
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=160
)

# -----------------------------
# 7️⃣ Load and process new documents
# -----------------------------
async def process_new_documents(text_splitter, vector_store):
    doc_data = await sync_to_async(lambda: list(doc.objects.filter(is_loaded=False)))()
    
    if len(doc_data) > 0:
        print("Processing new documents...")
        for document in doc_data:
            await process_document(document, vector_store)
    else:
        print("No new documents to process.")





# custom_prompt = PromptTemplate(
#     input_variables=["question"],
#     template="""
# Generate 3 different variations of this question focusing on:
# - The indicator names (e.g., SMA, RSI)
# - Time ranges (e.g., Jan–Mar 2025)
# - Any stock symbols mentioned

# Original question: {question}
# """
# )

# retriever = MultiQueryRetriever.from_llm(
#     retriever=retriever,
#     llm=llm,
#     include_original=True, 
#     prompt=custom_prompt,
# )
