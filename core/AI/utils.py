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


def flatten_indicators(indicators, parent_name=None):
    """
    Recursively flatten indicators into a list of records.
    Each record is a dict suitable for your split_json function.
    """
    flat_list = []

    for indicator in indicators:
        record = {
            "code": indicator.get('code', ''),
            "name": indicator.get('name', ''),
            "description": indicator.get('description', ''),
            "topic": indicator.get('topic', ''),
            "category": indicator.get('category', ''),
            "unit": indicator.get('unit', ''),
            "source": indicator.get('source', ''),
            "kpi_type": indicator.get('kpi_type', ''),
            "parent": parent_name or indicator.get('parent', ''),
            "version": indicator.get('version', ''),
        }
        flat_list.append(record)

        # Recursively flatten children
        children = indicator.get('child', [])
        if children:
            flat_list.extend(flatten_indicators(children, parent_name=indicator.get('name', '')))

    return flat_list


def split_json(file_path):
    import json

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_records = flatten_indicators(data)

    documents = []
    for i, record in enumerate(all_records):
        summary_text = f"""
Indicator: {record.get('name', '')} 
Code: {record.get('code', '')}
Description: {record.get('description', '')}

Topic: {record.get('topic', '')}
Category: {record.get('category', '')}
Unit: {record.get('unit', '')}
Source: {record.get('source', '')}
KPI Type: {record.get('kpi_type', '')}
Parent: { record.get("parent") or ""}
Version: {record.get('version', '')}
"""
        metadata = {
            "row_index": i,
            "code": record.get("code", ""),
            "name": record.get("name", ""),
            "topic": record.get("topic", ""),
            "category": record.get("category", ""),
            "unit": record.get("unit", ""),
            "source": record.get("source", ""),
            "kpi_type": record.get("kpi_type", ""),
            "parent": record.get("parent") or "",
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
        

        
        uuids = [str(uuid4()) for _ in range(len(documents))]

        vector_store.add_documents(documents=documents, ids=uuids)

        to_be_loaded_doc.is_loaded = True
        to_be_loaded_doc.save()
        print("Document processed and added to vector store.")
        return True

    except Exception as e:
        print(f"Error processing document {file_path}: {e}")
        return False




SYSTEM_RULES = """
You are MoPD Chat Bot, a Senior Economic Analyst for Ethiopia. Strictly adhere to the Context provided. Never invent or hallucinate data.

### 1. RESPONSE PROTOCOL
- GREETING ONLY: If input is only a greeting, reply exactly: "<p>Hello, I'm MoPD Chat Bot. How can I assist you?</p>"
- NULL DATA: If the question requires numeric, statistical, or documentary evidence and the required information is not found in the provided context:
  • Do not invent, estimate, or infer values.
  • You may explain or define the indicator conceptually using established economic knowledge, without including any numeric values.
  • Clearly state that the numeric information will be provided once the relevant data becomes available.
- GENERAL KNOWLEDGE EXCEPTION: If the question is general knowledge, conceptual, or definitional and does not require numeric values, statistics, or document-based data, answer directly using established economic knowledge.
- HIERARCHY: Prioritize Accuracy → Completeness → Trend Analysis → Clarity.

### 2. CALENDAR & DATA STANDARDS
- DEFAULT GEOGRAPHY: By default, all data is assumed to be Ethiopian data unless explicitly stated otherwise.
- DEFAULT CALENDAR: Use Ethiopian Calendar (EC).
- DUAL DATING: If both calendars exist, use format: "2017 EC (2024/25 GC)".
- NO CONVERSION: If only GC exists, show GC only. Never estimate or convert missing dates.
- DATA FIDELITY: Report all decimals, frequencies (Annual/Quarterly/Monthly), and Units (e.g., Billion ETB, %) exactly as found.

### 3. ANALYTICAL REQUIREMENTS
- INDICATOR DEFINITION: Start every data-driven response by defining the indicator and its economic significance.
- COMPREHENSIVE HISTORY: Describe ALL historical values found in context. Do not skip years or summarize only the latest data.
- TREND IDENTIFICATION: Analyze trajectory (Growth, Contraction, or Stability). Use comparative language (e.g., "Increased by X% compared to previous quarter").
- NO MARKDOWN: Never use #, **, or -. Use HTML tags only.

### 4. HTML STRUCTURE (FOR FLUTTER)
- HEADINGS: Use <h3> for Indicator names and <h4> for sub-sections.
- CONTENT: Use <p> for analysis and context sentences.
- DATA: Use <table> with <thead> and <tbody> for all numeric time-series. Include units in headers.
- METADATA: Use <ul> and <li> for Source, Version, and Category.
- CONSTRAINTS: No <html>, <head>, or <body> tags.

### 5. STYLE GUIDELINES
- Introduce every table with a sentence explaining what the numbers represent.
- Highlight patterns and volatility across periods.
- Avoid clutter: focus strictly on data relevant to the user's specific query.
"""


def run_chain(prompt, llm, conversation_list, context, question):
    """
    Invoke the llm chain with proper inputs.
    """

    messages = [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "user", "content": f"Context:\n{context}"},
    ]

    for m in conversation_list:
        messages.append({"role": m.type, "content": m.content})

    messages.append({"role": "user", "content": question})


    return llm.invoke(messages)

def format_docs(docs):
    """
    Format documents into a plain text string joined by double line breaks.
    """
    return "\n\n".join(doc.page_content for doc in docs)



async def run_chain_stream(llm, conversation_list, context, question):
    """
    Async generator that yields text chunks in real-time.
    """
    # Prepare the prompt messages
    messages = [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "user", "content": f"Context:\n{context}"},
    ]

    # Add history if available
    for m in conversation_list:
        messages.append({
            "role": m["role"],
            "content": m["content"]
        })

    messages.append({"role": "user", "content": question})

    # STREAMING: Iterate through the async stream
    async for chunk in llm.astream(messages):
        if hasattr(chunk, 'content'):
            yield chunk.content
        else:
            yield str(chunk)
