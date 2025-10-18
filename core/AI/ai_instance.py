import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from AI.utils import process_document
from .models import Document as doc
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

ChatOllama.model_rebuild()
# Initialize LLM
llm = ChatOllama(
    model="gpt-oss:latest",
    temperature=0.5,
    stream=False,
)

# Initialize Embeddings
embeddings = OllamaEmbeddings(
    model="nomic-embed-text:latest",
    base_url="http://127.0.0.1:11434"
)

# Set persistence directory
persist_directory = "./chroma_db"

vector_store = Chroma(
    collection_name="time-series",
    embedding_function=embeddings,
    persist_directory=persist_directory,
)

# Initialize text splitter for text-based documents (PDF, DOCX, TXT)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=160
)


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
        "k": 8,            
        "fetch_k": 100,    
        "lambda_mult": 0.3
    },
)



expanded_retriever = MultiQueryRetriever.from_llm(
    retriever=retriever,
    llm=llm,
    include_original=True
)

retriever = expanded_retriever


# compressor = LLMChainExtractor.from_llm(llm)
# rerank_retriever = ContextualCompressionRetriever(
#     base_retriever=expanded_retriever,
#     base_compressor=compressor
# )

# retriever = rerank_retriever