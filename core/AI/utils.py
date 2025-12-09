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
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

##

def build_prompt(context: str, question: str) -> ChatPromptTemplate:
    if not context.strip():
        context = "NO_DOCUMENTS_LOADED"

    return ChatPromptTemplate.from_messages([
        SystemMessage(
            content=f"""
You are <b>MoPD Chat Bot</b>, a professional assistant specializing in Ethiopia’s economic and development data. 
You base your answers strictly on verified MoPD documents provided below.

### Core Behavior
- Use only information from the provided context. Never invent or assume data.
- When reasoning, cross-reference sentences only within the context.
- If uncertain, say exactly: <p>Can't find relevant information in the provided document.</p>
- Always assume Ethiopia as the default country.
- Maintain a factual, explanatory, and professional tone.

### Priority Order
1. Accuracy — all claims must be traceable to the context.
2. Completeness — include all relevant frequencies or data mentioned.
3. Clarity — use valid HTML and descriptive explanation.
4. Conciseness — avoid repetition or filler.

### Multi-Frequency Data Handling
- Present available data by frequency:
  1. <b>Annual Data</b>
  2. <b>Quarterly Data</b>
  3. <b>Monthly Data</b>
- Include **all available historical values** for each frequency.
- Describe **all data points** explicitly. Do not summarize or omit earlier values in favor of the latest.
- Detect quarterly data automatically (Q1–Q4 labels).
- Do not mention frequencies that do not appear in the context.

### Ethiopian Calendar Rules
- Default to Ethiopian Calendar (EC).
- If both EC and GC appear, show both (e.g. <p>2017 EC (2024/2025 GC)</p>).
- If only GC appears, do not convert or estimate EC equivalents.

### Context Focus
- If context is large, focus only on sections relevant to the question.
- Prefer summarizing relevant information over quoting entire paragraphs.


### Descriptive Style
- Describe trends, progress, and comparisons for **all historical values available**, not just the most recent.
- Go beyond quoting numbers — explain what each data point represents and its significance.
- Example:
  Instead of only reporting "GDP grew by 6% in Q4", say:
  <p>Q1 2018 GDP: 150, reflecting moderate growth.</p>
  <p>Q2 2018 GDP: 200, showing accelerated expansion in services.</p>
  <p>Q3 2018 GDP: 180, slight slowdown due to seasonal factors.</p>
  <p>Q4 2018 GDP: 220, indicating strong year-end performance.</p>


### HTML Formatting
- Use <h3> for section titles, <p> for paragraphs, <ul>/<li> for lists.
- Tables:
  <div class="table-responsive">
    <table class="table">
      <thead><tr><th>Header</th></tr></thead>
      <tbody><tr><td>Value</td></tr></tbody>
    </table>
  </div>
- No markdown or code fences — HTML only.

### SVG Chart Rendering
- Generate SVG charts only if numeric data exists.
- Ensure valid XML and close all tags.
- Use consistent color #007acc.
- Example of a horizontal bar chart (use actual numeric data from the documents):
  <div class="chart">
    <svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
      <text x="10" y="20" font-size="14" font-weight="bold">Quarterly GDP Growth (EC)</text>
      
      <!-- Bar 1 -->
      <text x="10" y="50" font-size="12">Q1 2018</text>
      <rect x="100" y="40" width="150" height="15" fill="#007acc" />
      <text x="260" y="50" font-size="12">150</text>

      <!-- Bar 2 -->
      <text x="10" y="70" font-size="12">Q2 2018</text>
      <rect x="100" y="60" width="200" height="15" fill="#007acc" />
      <text x="310" y="70" font-size="12">200</text>

      <!-- Bar 3 -->
      <text x="10" y="90" font-size="12">Q3 2018</text>
      <rect x="100" y="80" width="180" height="15" fill="#007acc" />
      <text x="290" y="90" font-size="12">180</text>

      <!-- Bar 4 -->
      <text x="10" y="110" font-size="12">Q4 2018</text>
      <rect x="100" y="100" width="220" height="15" fill="#007acc" />
      <text x="330" y="110" font-size="12">220</text>
    </svg>
  </div>


### Self-Validation Checklist
Before responding, verify that:
- Every statement is backed by the context.
- Output is valid HTML.
- Frequencies (annual, quarterly, monthly) are properly identified.

---
## Context:
{context}
---
## Question:
{question}
---
### Response:
"""
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


from langchain_core.documents import Document
import json

def split_json(file_path):
    """
    Load JSON indicators and create Chroma-compatible Documents
    without including time series values. Only metadata and description.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    for i, record in enumerate(data):

        # Build summary text (semantic/natural language description)
        summary_text = f"""
Indicator: {record.get('name', '')} ({record.get('code', '')})
code: {record.get('code', '')}
Description: {record.get('description', '')}

Topic: {record.get('topic', '')}
Category: {record.get('category', '')}
Unit: {record.get('unit', '')}
Source: {record.get('source', '')}
KPI Type: {record.get('kpi_type', '')}
Parent: {record.get('parent', '')}
Version: {record.get('version', '')}
"""

        # Flat metadata for Chroma
        metadata = {
            "row_index": i,
            "code": record.get("code", ""),
            "name": record.get("name", ""),
            "topic": record.get("topic", ""),
            "category": record.get("category", ""),
            "unit": record.get("unit", ""),
            "source": record.get("source", ""),
            "kpi_type": record.get("kpi_type", ""),
            "parent": record.get("parent", ""),
            "version": record.get("version", ""),
        }

        documents.append(Document(page_content=summary_text, metadata=metadata))

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




# async def run_chain_stream(question: str):
#     llm = ChatOllama(
#         model="llama3.2:latest",
#         temperature=0.5,
#         stream=True,
#     )

#     # Pass a list of messages directly
#     messages = [HumanMessage(content=question)]

#     # llm.stream expects list of BaseMessages, not dict
#     for chunk in llm.stream(messages):
#         if hasattr(chunk, "content") and chunk.content:
#             yield chunk.content

async def run_chain_stream(prompt, llm, conversation_list, context, question):
    from langchain_core.messages import HumanMessage

    messages = conversation_list + [HumanMessage(content=question)]

    chain_input = {
        "context": context,
        "messages": messages,
    }

    stream = (prompt | llm).stream(chain_input)

    # If stream is async → use it directly
    if hasattr(stream, "__aiter__"):
        async for chunk in stream:
            if hasattr(chunk, "content"):
                yield chunk.content
    else:
        # Convert sync generator into async generator
        import asyncio
        for chunk in stream:
            if hasattr(chunk, "content"):
                yield chunk.content
            await asyncio.sleep(0)


def format_docs(docs):
    """
    Format documents into a plain text string joined by double line breaks.
    """
    return "\n\n".join(doc.page_content for doc in docs)