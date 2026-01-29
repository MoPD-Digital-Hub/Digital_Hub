from langchain_core.documents import Document
from uuid import uuid4
import os
import json
from asgiref.sync import sync_to_async
from .rules import SYSTEM_RULES, MINISTRY_SCORE_SYSTEM_RULES

def split_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    for item in data:
        if not item: continue
        
        page_content = item.get("page_content", "")
        metadata = item.get("metadata", {}) 

        documents.append(
            Document(
                page_content=page_content, 
                metadata=metadata
            )
        )
    return documents

async def process_document(to_be_loaded_doc, vector_store) -> bool:
    """
    Process a single document file, split JSON content into documents,
    and add them to the Milvus vector store with dynamic metadata.
    """
    try:
        file_path = to_be_loaded_doc.file.path
        ext = os.path.splitext(file_path)[1].lower()
        print(f"Loading document: {file_path}")

        if ext != ".json":
            print(f"Unsupported file extension {ext}, skipping.")
            return False

        documents = split_json(file_path)

        if not documents:
            print(f"No documents found in {file_path}.")
            return False

        ids = [str(uuid4()) for _ in range(len(documents))]

        await sync_to_async(vector_store.add_documents)(
            documents=documents,
            ids=ids
        )

    
        to_be_loaded_doc.is_loaded = True
        await sync_to_async(to_be_loaded_doc.save)()

        print(f"{len(documents)} documents processed and added to vector store: {file_path}")
        return True

    except Exception as e:
        print(f"Error processing document {file_path}: {e}")
        return False


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



async def run_chain_stream(llm, conversation_list, context, question, intent=None):
    """
    Async generator that yields text chunks in real-time based on classified intent.
    """
    
    if intent == "MINISTRY_SCORE":
        selected_system_rule = MINISTRY_SCORE_SYSTEM_RULES
    elif intent == "TIME_SERIES":
        selected_system_rule = SYSTEM_RULES 
    else:
        selected_system_rule = SYSTEM_RULES 

    messages = [
        {"role": "system", "content": selected_system_rule},
        {"role": "user", "content": f"Context:\n{context}"},
    ]

    for m in conversation_list:
        role = m.get("role") if isinstance(m, dict) else m.type
        content = m.get("content") if isinstance(m, dict) else m.content
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    async for chunk in llm.astream(messages):
        if hasattr(chunk, 'content'):
            yield chunk.content
        else:
            yield str(chunk)