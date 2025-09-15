from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from langchain.tools import tool
import requests
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    UnstructuredWordDocumentLoader,
    TextLoader,
    CSVLoader,
    UnstructuredExcelLoader,
)
import pandas as pd
import os
import json

##


@tool
def get_policy_area(year: str) -> str:
 """Fetches policy areas using a REST API."""
 url = f"https://dpmes.mopd.gov.et/api/digital-hub/all-policy-area/?year=2017&quarter=3month"
 response = requests.get(url)
 return response.json()["data"]

def build_prompt(context: str, question: str) -> ChatPromptTemplate:
    """
    Build a user-friendly and descriptive prompt template for the MoPD Chat Bot.
    Responses are in clean HTML format without markdown code fences.
    """
    return ChatPromptTemplate.from_messages([
        SystemMessage(
            content=f'''
                You are **MoPD Chat Bot**, a friendly and professional assistant specializing in Ethiopia's economic data.
                Your goal is to provide **clear, descriptive, and human-friendly explanations** using only the verified documents loaded into the system.

                Guidelines:
                - Always answer using the provided documents; do NOT invent or assume any data.
                - Extract insights, trends, and relevant context from the documents to make the answer informative.
                - Clearly indicate whether information is **verified** (from documents) or **not found**.
                - If no relevant information exists, reply: "Can't find relevant information in the provided document."
                - If a question is unrelated to economics, answer naturally without adding economic concepts.
                - If a country is not mentioned, assume the question is about Ethiopia.
                - Explain numbers, percentages, or statistics in simple terms, providing context from the document.
                - Avoid formulas, raw calculations, or technical jargon unless necessary for clarity.
                - Respond politely and in a conversational tone, while staying professional.

                **Ethiopian Calendar Conversion**:
                - EFY/EC years can be approximated to Gregorian by adding 7 years.

                **HTML Formatting**:
                - Use `<h3>` for headings and `<p>` for body text.
                - Use `<ul>` and `<li>` for lists.
                - For tables, wrap them in `<div class="table-responsive">` and use `<table class="table">` with `<thead>` for headers.

                Greeting behavior:
                - If a user says "hi," "hello," or similar, introduce yourself as **MoPD Chat Bot**, mention you answer based on verified documents, and briefly list the loaded documents.

                ## Context:
                {context}

                ## Question:
                {question}

                ## Response:
                Provide a descriptive and structured answer following the HTML format above.
                - Explain the data with context and trends as described in the documents.
                - If no relevant information is found, clearly state: "Can't find relevant information in the provided document."
            '''
        ),
        MessagesPlaceholder(variable_name="messages"),
    ])


def split_pdf_or_txt(raw_docs, text_splitter):
    documents = []
    for raw_doc in raw_docs:
        splits = text_splitter.split_text(raw_doc.page_content)
        for chunk in splits:
            metadata = raw_doc.metadata if hasattr(raw_doc, "metadata") else {}
            documents.append(Document(page_content=chunk, metadata=metadata))
    return documents

def split_docx(raw_docs):
    # If loader already splits well, just return raw_docs as Documents list
    # Or implement paragraph splitting if needed
    return raw_docs

def split_excel(file_path):
    df = pd.read_excel(file_path)
    documents = []
    for i, row in df.iterrows():
        row_dict = row.to_dict()

        # Convert entire row dict to JSON string as content
        content = json.dumps(row_dict, ensure_ascii=False)

        # Create Document with content and metadata (including row index)
        documents.append(
            Document(page_content=content, metadata={"row_index": i, **row_dict})
        )
    return documents

def split_csv(file_path):
    documents = []
    df = pd.read_csv(file_path)
    for i, row in df.iterrows():
        content = row.to_json()
        documents.append(Document(page_content=content, metadata={"row": i}))
    return documents


def split_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)  # expect a list of dicts

    documents = []
    for i, record in enumerate(data):
        content = json.dumps(record, ensure_ascii=False)
        documents.append(Document(page_content=content, metadata={"row_index": i, **record}))
    return documents

def process_document(to_be_loaded_doc, text_splitter, vector_store) -> bool:
    try:
        file_path = to_be_loaded_doc.file.path
        ext = os.path.splitext(file_path)[1].lower()

        print(f"Loading document: {file_path}")

        if ext == ".pdf":
            loader = PyMuPDFLoader(file_path)
            raw_docs = loader.lazy_load()
            documents = split_pdf_or_txt(raw_docs, text_splitter)

        elif ext == ".docx":
            loader = UnstructuredWordDocumentLoader(file_path)
            raw_docs = loader.lazy_load()
            documents = split_docx(raw_docs)

        elif ext == ".txt":
            loader = TextLoader(file_path)
            raw_docs = loader.lazy_load()
            documents = split_pdf_or_txt(raw_docs, text_splitter)

        elif ext == ".xlsx":
            documents = split_excel(file_path)

        elif ext == ".csv":
            documents = split_csv(file_path)

        elif ext == ".json":
            documents = split_json(file_path)

        else:
            print(f"Unsupported file extension {ext}, skipping.")
            return False

        doc_ids = [f"doc-{to_be_loaded_doc.id}-{i}" for i in range(len(documents))]
        vector_store.add_documents(documents=documents, ids=doc_ids)

        to_be_loaded_doc.is_loaded = True
        to_be_loaded_doc.save()
        print("Document processed and added to vector store.")
        return True

    except Exception as e:
        print(f"Error processing document {file_path}: {e}")
        return False




def run_chain(prompt, llm, conversation_list, context, question):
    """
    Invoke the llm chain with proper inputs.
    """
    from langchain_core.messages import HumanMessage

    chain_input = {
        "context": context,
        "messages": conversation_list + [HumanMessage(content=question)],
    }
    return (prompt | llm).invoke(chain_input)

def format_docs(docs):
    """
    Format documents into a plain text string joined by double line breaks.
    """
    return "\n\n".join(doc.page_content for doc in docs)