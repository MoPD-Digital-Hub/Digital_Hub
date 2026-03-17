from asgiref.sync import sync_to_async
from .models import Document as doc
from AI.shared import process_document
from celery import shared_task
from AI.models import ChatInstance
from AI.application import generate_answer



# Load and process new documents
async def process_new_documents(text_splitter, vector_store):
    doc_data = await sync_to_async(lambda: list(doc.objects.filter(is_loaded=False)))()
    
    if len(doc_data) > 0:
        print("Processing new documents...")
        for document in doc_data:
            await process_document(document, vector_store)
    else:
        print("No new documents to process.")


@shared_task(bind=True)
def generate_answer_task(self, chat_instance_id, question, request_id=None):
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id, is_deleted=False)
    except ChatInstance.DoesNotExist:
        return {
            "status": "FAILURE",
            "error": {"code": "INSTANCE_NOT_FOUND", "message": "Instance doesn't exist"},
            "request_id": request_id,
        }

    result = generate_answer(chat_instance, question)
    return {
        "status": "SUCCESS" if result.status_code < 400 else "FAILURE",
        "request_id": request_id,
        "data": {
            "chat_instance_id": chat_instance_id,
            "question": question,
            "answer": result.answer,
            "route": result.route,
            "token_usage": result.token_usage,
        },
        "error": result.error,
        "message": result.message,
        "status_code": result.status_code,
    }
