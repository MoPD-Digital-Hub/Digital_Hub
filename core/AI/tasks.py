from asgiref.sync import sync_to_async
from .models import Document as doc
from AI.utils import process_document



# Load and process new documents
async def process_new_documents(text_splitter, vector_store):
    doc_data = await sync_to_async(lambda: list(doc.objects.filter(is_loaded=False)))()
    
    if len(doc_data) > 0:
        print("Processing new documents...")
        for document in doc_data:
            await process_document(document, vector_store)
    else:
        print("No new documents to process.")