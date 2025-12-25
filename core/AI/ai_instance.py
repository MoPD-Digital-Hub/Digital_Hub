import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, list_collections, MilvusException, db, utility
from AI.utils import process_document
from .models import Document as doc
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import MilvusClient
from langchain_core.prompts import PromptTemplate

llm = ChatOpenAI(
    openai_api_base="http://localhost:8000/v1",
    openai_api_key="EMPTY",
    model="openai/gpt-oss-20b",
    streaming=True,
    temperature = 0.2
)

# -----------------------------
# 2️⃣ Initialize embeddings
# -----------------------------
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

vector_store = Milvus(
    embedding_function=embeddings,
    connection_args={"alias": "default"},
    index_params={"index_type": "FLAT", "metric_type": "L2"},
    consistency_level="Strong",
    drop_old=False, 
)



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
doc_data = doc.objects.filter(is_loaded=False)
if doc_data.count() > 0:
    print("Processing new documents...")
    for document in doc_data:
        process_document(document, text_splitter, vector_store)
else:
    print("No new documents to process.")

# -----------------------------
# 8️⃣ Initialize retriever
# -----------------------------

# retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})

retriever = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 5,            
        "fetch_k": 15,    
        "lambda_mult": 0.3
    },
)

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
