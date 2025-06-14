import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from AI.utils import process_document, format_docs
from .models import Document as doc
from .models import LoadedFile
from langchain_community.embeddings import HuggingFaceEmbeddings

# Initialize LLM
llm = ChatOllama(
    model="llama3.2",
    temperature=0.7,
    stream=True,
)

# Initialize Embeddings
embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large")

# Set persistence directory
persist_directory = "./chroma_db"

# Initialize Chroma vector store
vector_store = Chroma(
    collection_name="foo",
    embedding_function=embeddings,
    persist_directory=persist_directory,
)

# Initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=250,
)

doc_data = doc.objects.filter(is_loaded=False)

# Load and process documents if vector store is empty or new docs exist
if not os.path.exists(persist_directory) or doc_data.count() > 0:
    print("Loading and processing documents...")

    for document in doc_data:
        process_document(document, text_splitter, vector_store)
else:
    print("Using persisted vector store.")

# Initialize retriever
retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})