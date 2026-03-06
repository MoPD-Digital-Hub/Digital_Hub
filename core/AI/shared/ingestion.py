import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from asgiref.sync import sync_to_async
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from AI.platform.observability import increment, set_last_ingestion_report, timed

from .constants import REQUIRED_METADATA_KEYS_ANY

text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=160)


def split_json(file_path):
    with open(file_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    documents = []
    for item in data:
        if not item:
            continue
        documents.append(
            Document(
                page_content=item.get("page_content", ""),
                metadata=item.get("metadata", {}),
            )
        )
    return documents


async def process_document(to_be_loaded_doc, vector_store) -> bool:
    try:
        file_path = to_be_loaded_doc.file.path
        if os.path.splitext(file_path)[1].lower() != ".json":
            return False

        documents = split_json(file_path)
        if not documents:
            return False

        valid_docs = []
        report = {
            "processed": len(documents),
            "loaded": 0,
            "skipped": 0,
            "errors": 0,
            "details": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "file": file_path,
        }

        for idx, document in enumerate(documents):
            meta = getattr(document, "metadata", {}) or {}
            if not any(k in meta and meta.get(k) for k in REQUIRED_METADATA_KEYS_ANY):
                report["skipped"] += 1
                report["details"].append(
                    {
                        "index": idx,
                        "reason": "missing_required_metadata",
                        "metadata_keys": list(meta.keys()),
                    }
                )
                increment("ingestion_skipped")
                continue
            valid_docs.append(document)

        if not valid_docs:
            report["errors"] += 1
            set_last_ingestion_report(report)
            return False

        ids = [str(uuid4()) for _ in valid_docs]
        done = timed("ingestion_vectorstore_add_ms")
        await sync_to_async(vector_store.add_documents)(documents=valid_docs, ids=ids)
        done()

        to_be_loaded_doc.is_loaded = True
        await sync_to_async(to_be_loaded_doc.save)()

        report["loaded"] = len(valid_docs)
        set_last_ingestion_report(report)
        increment("ingestion_loaded")
        return True
    except Exception:
        increment("ingestion_errors")
        return False
