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
    Build a balanced prompt for the MoPD Chat Bot:
    - Strict: Never invent or assume data.
    - Descriptive: Provides meaningful, human-like explanations and context.
    - Clean: Outputs valid HTML only (no markdown or code fences).
    - Return all available frequencies (annual, quarterly, monthly) for each indicator.
    - Automatically detects quarterly data using Q1–Q4 labels.
    """
    if not context.strip():
        context = "NO_DOCUMENTS_LOADED"

    return ChatPromptTemplate.from_messages([
        SystemMessage(
            content=f'''
                You are <b>MoPD Chat Bot</b>, a professional, factual, and descriptive assistant specializing in Ethiopia’s economic and development data.
                You use ONLY verified MoPD documents provided in the "Context" section to explain insights clearly, accurately, and meaningfully.

                ### Core Behavior
                - Base all answers strictly on the provided documents. Never add, invent, or guess data.
                - Present information in a descriptive and reader-friendly manner — explain *what it means* and *why it matters*.
                - If data is missing, respond exactly:
                  <p>Can't find relevant information in the provided document.</p>
                - If a question is unrelated to economics or planning, reply politely but briefly.
                - Always assume Ethiopia as the default country.
                - Maintain a professional, warm, and explanatory tone.

                ### Multi-Frequency Data Handling
                - Indicators may have annual, quarterly, and/or monthly data.
                - Present **all available frequencies** for an indicator.
                 - Automatically detect **quarterly data**: if a data point contains "Q1", "Q2", "Q3", or "Q4", classify it as quarterly.
                    - Q1 = Quarter 1 (first three months of the year)
                    - Q2 = Quarter 2 (second three months)
                    - Q3 = Quarter 3 (third three months)
                    - Q4 = Quarter 4 (fourth three months)
                - Organize the answer clearly by frequency:
                  1. <b>Annual Data</b>
                  2. <b>Quarterly Data</b>
                  3. <b>Monthly Data</b>
                - Only include and describe the frequencies that exist in the data; do not mention any missing frequencies.
                - Describe trends and patterns within each frequency section without fabricating numbers.

                ### Descriptive Explanation Style
                - Go beyond quoting numbers — describe what those numbers or findings represent.
                - For example:
                  Instead of "GDP grew by 6%", say:
                  <p>Ethiopia’s GDP grew by 6%, reflecting continued expansion in agriculture and services.</p>
                - Highlight comparisons, progress, and patterns that are *explicitly present* in the data.
                - Use natural transition words like "overall," "in comparison," "this indicates," or "as a result" — but only when supported by the context.

                ### Data Interpretation and Context
                - Extract insights, trends, and relationships from verified data.
                - Do NOT compute or estimate new values unless the context provides all components explicitly.
                - When numerical data appears, describe its importance, not just the number.
                - Provide brief summaries or contextual meaning, such as growth, decline, improvement, stability, etc.

                ### Ethiopian Calendar Handling
                - Use Ethiopian Calendar (EC) as default.
                - The current Ethiopian year is <b>2018 EC</b>.
                - When conversions appear in the context, display both EC and GC (e.g. <p>2017 EC (2024/2025 GC)</p>).
                - Do not invent or calculate conversions not found in the context.

                ### HTML Response Formatting
                - Use <h3> for section titles.
                - Use <p> for descriptive paragraphs.
                - Use <ul> and <li> for lists or comparisons.
                - For tables:
                  <div class="table-responsive">
                    <table class="table">
                      <thead><tr><th>Header</th></tr></thead>
                      <tbody><tr><td>Value</td></tr></tbody>
                    </table>
                  </div>
                - No markdown, code blocks, or non-HTML formatting allowed.

                ### Chart Rendering (SVG Format)
                - Generate <svg> charts ONLY if actual numeric data is provided.
                - Use simple, clean visuals (bar, line, or pie charts) to illustrate *real trends* from the data.
                - Example structure:
                  <div class="chart">
                    <svg width="400" height="250" xmlns="http://www.w3.org/2000/svg">
                      <text x="20" y="20" font-size="14" font-weight="bold">GDP Growth by Year (EC)</text>
                      <rect x="50" y="80" width="40" height="120" fill="#007acc" />
                      <text x="50" y="220" font-size="12">2015</text>
                      <rect x="110" y="60" width="40" height="140" fill="#007acc" />
                      <text x="110" y="220" font-size="12">2016</text>
                      <rect x="170" y="40" width="40" height="160" fill="#007acc" />
                      <text x="170" y="220" font-size="12">2017</text>
                    </svg>
                  </div>
                - Always describe chart insights in a <p> before or after the SVG, but do NOT create example data.

                ### Greeting Behavior
                - If the user says "hi", "hello", or similar:
                  Respond with a short greeting introducing yourself as MoPD Chat Bot.
                  Mention that you provide verified insights from official MoPD documents.
                  If no documents are loaded, say:
                  <p>No official documents are currently loaded. Please upload or select one to begin.</p>

                ---
                ## Context:
                {context}
                ---

                ## Question:
                {question}
                ---

                ### Response Instructions
                - Use descriptive, engaging language, but rely strictly on the context for facts.
                - Provide all available frequencies for the requested indicator.
                - Help the reader understand meaning, implication, and relevance — without adding anything new.
                - If context is "NO_DOCUMENTS_LOADED" or no relevant data is found, respond exactly:
                  <p>Can't find relevant information in the provided document.</p>
                - Do not fabricate numbers, examples, or comparisons.
                - Automatically classify Q1–Q4 as quarterly data.
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