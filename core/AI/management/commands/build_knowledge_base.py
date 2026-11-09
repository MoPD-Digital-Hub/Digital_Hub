import json

from django.core.management.base import BaseCommand, CommandError

from AI.infrastructure import ensure_collection, get_vector_store
from AI.infrastructure.constants import COLLECTION_NAME
from AI.knowledge_base import KB_SOURCE, build_documents
from dashboard import dpmes2

BATCH_SIZE = 64


class Command(BaseCommand):
    help = (
        "Rebuild the AI knowledge base from the live time-series and DPMES APIs: one record per "
        "indicator, ministry, policy area and strategic goal. Replaces the records from the previous "
        "run; documents uploaded through the admin are left alone."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Build and count the records without loading them.")
        parser.add_argument("--output", help="Also write the records to this JSON file, in the admin upload format.")
        parser.add_argument("--skip-dpmes", action="store_true", help="Only load time-series indicators.")
        parser.add_argument("--year", type=int, help="Ethiopian year for DPMES lookups (default: last completed year).")

    def handle(self, *args, **options):
        period = {"year": options["year"]} if options["year"] else None
        try:
            records = build_documents(
                include_dpmes=not options["skip_dpmes"],
                period=period,
                log=self.stdout.write,
            )
        except (dpmes2.DPMES2Error, OSError, ValueError) as exc:
            raise CommandError(f"Could not fetch the source data: {exc}") from exc

        if not records:
            raise CommandError("The APIs returned no records; nothing was changed.")

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as handle:
                json.dump(
                    [{"page_content": doc.page_content, "metadata": doc.metadata} for _, doc in records],
                    handle,
                    ensure_ascii=False,
                    indent=1,
                )
            self.stdout.write(f"Wrote {len(records)} records to {options['output']}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry run: {len(records)} records built, nothing loaded."))
            return

        client = ensure_collection()
        if client is None:
            raise CommandError("Milvus is unreachable (check MILVUS_URI); nothing was changed.")
        vector_store = get_vector_store()

        vector_store.delete(expr=f'kb_source == "{KB_SOURCE}"')
        for start in range(0, len(records), BATCH_SIZE):
            batch = records[start : start + BATCH_SIZE]
            vector_store.add_documents(documents=[doc for _, doc in batch], ids=[key for key, _ in batch])
            self.stdout.write(f"  loaded {min(start + BATCH_SIZE, len(records))}/{len(records)}")

        client.flush(collection_name=COLLECTION_NAME)
        total = client.get_collection_stats(collection_name=COLLECTION_NAME).get("row_count")
        self.stdout.write(self.style.SUCCESS(
            f"Knowledge base rebuilt: {len(records)} records loaded; collection '{COLLECTION_NAME}' now holds {total}."
        ))
