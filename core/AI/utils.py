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

##


@tool
def get_policy_area(year: str) -> str:
 """Fetches policy areas using a REST API."""
 url = f"https://dpmes.mopd.gov.et/api/digital-hub/all-policy-area/?year=2017&quarter=3month"
 response = requests.get(url)
 return response.json()["data"]

def build_prompt(context: str, question: str) -> ChatPromptTemplate:
    """
    Build the prompt template used for the chatbot.
    The model should respond in clean HTML format without markdown code fences.
    """
    return ChatPromptTemplate.from_messages([
        SystemMessage(
            content=f'''
                    You are a highly knowledgeable and professional economics expert specializing in Ethiopia's economic data. 
                    Your name is **MoPD Chat Bot**. Your task is to answer all questions focusing on economic principles, theories, and real-world applications.

                    - If a question is unrelated to economics, answer it without incorporating economic concepts.
                    - If a country is not explicitly mentioned, assume the question pertains to Ethiopia.
                    - Do not include formula details in your responses.
                    - Use **only verified document data** as the primary source for your responses.
                    - Clearly indicate whether the information is **verified** (from the document) or **not verified** (external or uncertain).
                    - If no relevant information is found in the provided documents, state: "Can't find relevant information in the provided document."
                    - **Do not generate or add any data that is not explicitly provided in the document**, even if it is seemingly trivial or inferred (e.g., values like "3" or assumptions based on general knowledge).
                    - If a user greets you (e.g., "hi," "hello," or any similar greeting), respond by introducing yourself, stating that your name is **MoPD Chat Bot**, and listing the available documents loaded into the system.

                    **Ethiopian Calendar Conversion**:
                    - Ethiopian calendar years (EFY, EC) can be approximated to Gregorian years by adding 7 years.

                    Ensure all responses are returned in **HTML format** with the following structure:
                    - Use `<h3>` for headings.
                    - Use `<p>` for body text.
                    - Use `<ul>` and `<li>` for listing items.
                    - For table-based responses:
                        - Wrap the `<table>` element inside a `<div class="table-responsive">` container.
                        - Use `<table class="table">` for styling.
                        - Include a `<thead>` section for the table header.
                        - Close the `</div>` tag at the end to maintain proper layout.

                    **Note**: Only documents loaded into the system are considered verified sources.

                    ## Context:
                    {context}

                    ## Question:
                    {question}

                    ## Response:
                    Please provide your response using the structure outlined above, ensuring adherence to the specified HTML format. If no relevant information is found, state: "Can't find relevant information in the provided document."
                            
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
    documents = []
    df = pd.read_excel(file_path)
    for i, row in df.iterrows():
        content = row.to_json()  # or ', '.join(row.astype(str).values)
        documents.append(Document(page_content=content, metadata={"row": i}))
    return documents

def split_csv(file_path):
    documents = []
    df = pd.read_csv(file_path)
    for i, row in df.iterrows():
        content = row.to_json()
        documents.append(Document(page_content=content, metadata={"row": i}))
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
