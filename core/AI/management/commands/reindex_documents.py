import asyncio

from django.core.management.base import BaseCommand
from pymilvus import MilvusClient

from AI.infrastructure import ensure_collection, get_vector_store
from AI.infrastructure.constants import COLLECTION_NAME, DEFAULT_MILVUS_URI, EMBEDDING_DIM
from AI.infrastructure import vectorstore as vectorstore_module
from AI.models import Document
from AI.shared import text_splitter
from AI.tasks import process_new_documents


class Command(BaseCommand):
    help = (
        "Re-embed every knowledge-base document. Required after changing the "
        "embedding model, since the Milvus collection is tied to the vector size."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop-collection",
            action="store_true",
            help=f"Drop the '{COLLECTION_NAME}' collection first (recreated with dim={EMBEDDING_DIM}).",
        )

    def handle(self, *args, **options):
        if options["drop_collection"]:
            client = ensure_collection()
            if client is None:
                self.stderr.write(self.style.ERROR("Milvus is unreachable; nothing dropped."))
                return
            if client.has_collection(COLLECTION_NAME):
                client.drop_collection(COLLECTION_NAME)
                self.stdout.write(self.style.WARNING(f"Dropped collection {COLLECTION_NAME}."))
            vectorstore_module._vector_store = None
            ensure_collection()

        reset = Document.objects.update(is_loaded=False)
        self.stdout.write(f"Marked {reset} document(s) for re-ingestion.")

        vector_store = get_vector_store()
        asyncio.run(process_new_documents(text_splitter, vector_store))

        loaded = Document.objects.filter(is_loaded=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"Re-indexed {loaded}/{Document.objects.count()} document(s) with {EMBEDDING_DIM}-dim vectors."
        ))
