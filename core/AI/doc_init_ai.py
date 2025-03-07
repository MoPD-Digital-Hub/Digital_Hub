from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough

from langchain_core.messages import AIMessage, HumanMessage , SystemMessage


from langchain.retrievers.self_query.base import SelfQueryRetriever

import os
import asyncio
from multiprocessing import Pool
from .models import Document as doc
from .models import LoadedFile

doc_data = doc.objects.filter(is_loaded = False)
all_docs = doc.objects.all().count()


# Initialize LLM
llm = ChatOllama(
    model="llama3.2",
    temperature=0.7,
    stream=True,
)

# Initialize Embeddings
embeddings = OllamaEmbeddings(
    model="znbang/bge:large-en-v1.5-f16",
)

# Set persistence directory
persist_directory = "./chroma_db"

# Initialize Chroma vector store
vector_store = Chroma(
    collection_name="foo",
    embedding_function=embeddings,
    persist_directory=persist_directory  # Add persistence directory
)

# Initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,  # Number of characters per chunk
    chunk_overlap=250,  # Overlap between chunks to maintain context
)


loaded_file = LoadedFile.objects.filter().first()
# Load and process documents if vector store is empty
if not os.path.exists(persist_directory) or doc_data.count() > 0:
    print("Loading and processing documents...")

    # Load PDF using PyMuPDFLoader
    

    def load_and_split_documents( to_be_loaded_doc):
        """
        Loads and splits documents into chunks using the text splitter.
        """
        try:
            print("document loading -----> ", to_be_loaded_doc.file.path)

            loader = PyMuPDFLoader(to_be_loaded_doc.file.path)
            raw_docs = loader.lazy_load()
            documents = [
                Document(page_content=chunk, metadata=raw_doc.metadata)
                for raw_doc in raw_docs
                for chunk in text_splitter.split_text(raw_doc.page_content)
            ]
            # Assign unique string IDs to documents
            document_ids = [f"doc-{to_be_loaded_doc.id}-{i}" for i in range(len(documents))]
        
            # Add documents to the vector store and persist data
            try:
                vector_store.add_documents(documents=documents, ids=document_ids)
                to_be_loaded_doc.is_loaded = True
                to_be_loaded_doc.save()
                print("Documents added successfully and persisted!")
            except Exception as e:
                print(f"Error adding documents to vector store: {e}")
        except Exception as e:
            print(f"Error loading or processing documents: {e}")
            return []
    
    
    
    for doc_ii in doc_data:
        load_and_split_documents(doc_ii)
else:
    print("Using persisted vector store.")

# Initialize retriever
retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})

# Set up document formatting
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Define a prompt template for the chain


prompt  =ChatPromptTemplate.from_messages(
    [
        SystemMessage(
            content='''
            You are a highly knowledgeable and professional economics expert. 
            Your task is to answer all questions with a focus on economic principles, theories, and real-world applications.
            You are an economics expert specializing in Ethiopia's economic data.
            
            - If you are asked a question that is not related to economics, answer it without relating it to economics.
            - If the country is not mentioned in an economic question, assume it pertains to Ethiopia.
            - Do not display any formula details. 
            - Use **only the verified document data** as the primary source for your responses.
            - Clearly indicate if the provided information is **verified** (from the document) or **not verified** (external or uncertain).
            - If no relevant information is found in the provided documents, return a message stating: "Can't find relevant information in the provided document."

            **Ethiopian Calendar Conversion**:
            - Ethiopian calendar years (EFY, EC) are converted to Gregorian years approximately by adding 7 years.

            Ensure all responses are returned in **HTML format** with the following structure:
            - Use <h3> for headings.
            - Use <p> for body text.
            - Use <ul> and <li> for listing items.
            - For table-based responses:
              - Wrap the <table> element inside a <div class="table-responsive"> container.
              - Use <table class="table"> for styling.
              - Include a <thead> section for the table header.
              - Close the </div> at the end for proper layout.

            **Note**: Only the documents loaded into the system are considered verified sources.
            
            ## Context:
            {context}

            ## Question:
            {question}

            ## Response:
            Please provide your response following the structure above, ensuring all outputs adhere to the specified HTML format. If no information is found in the document, state: "Can't find relevant information in the provided document."
            '''
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)




# Build the chain of operations
chain = (
    {
        'context': retriever | format_docs,  # Retrieve and format relevant context
        'question': RunnablePassthrough(),  # Pass user query
    }
    | prompt  # Combine inputs into a single prompt
    | llm  # Get response from the model
)