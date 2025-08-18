import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from AI.utils import process_document
from .models import Document as doc

ChatOllama.model_rebuild()
# Initialize LLM
llm = ChatOllama(
    model="gpt-oss:latest",
    temperature=0.2,
    stream=True,
)

# Initialize Embeddings
embeddings = OllamaEmbeddings(
    model="znbang/bge:large-en-v1.5-f16",
    base_url="http://127.0.0.1:11434"
)

# Set persistence directory
persist_directory = "./chroma_db"

vector_store = Chroma(
    collection_name="foo",
    embedding_function=embeddings,
    persist_directory=persist_directory,
)

# Initialize text splitter for text-based documents (PDF, DOCX, TXT)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)


doc_data = doc.objects.filter(is_loaded=False)

# Load and process documents if vector store is empty or new docs exist
if not os.path.exists(persist_directory) or doc_data.count() > 0:
    print("Loading and processing documents...")

    for document in doc_data:
        process_document(document, text_splitter, vector_store)  # pass both
else:
    print("Using persisted vector store.")

# Initialize retriever
retriever = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 4,        # number of chunks to return
        "fetch_k": 10, # candidate pool before reranking
        "lambda_mult": 0.5  # balance relevance vs diversity
    }
)
