from django.db.models.signals import post_save
from django.dispatch import receiver
from threading import Thread
from .models import Document
from AI.ai_instance import process_new_documents, text_splitter, get_vector_store
import asyncio

def run_async_task():
    vector_store = get_vector_store()
    asyncio.run(
        process_new_documents(text_splitter, vector_store)
    )

@receiver(post_save, sender=Document)
def trigger_document_processing(sender, instance, created, **kwargs):
    if not created:
        return

    Thread(target=run_async_task, daemon=True).start()