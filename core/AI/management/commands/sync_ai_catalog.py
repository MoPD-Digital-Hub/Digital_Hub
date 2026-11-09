from django.core.management.base import BaseCommand, CommandError

from AI.v2.catalog import sync
from AI.v2.llm import LLMError
from dashboard import dpmes2


class Command(BaseCommand):
    help = (
        "Sync the v2 entity catalog (indicators, organizations, policy areas, goals) from the "
        "time-series and DPMES APIs, and embed new or changed entries. Safe to run repeatedly; "
        "schedule it daily so new indicators become answerable."
    )

    def add_arguments(self, parser):
        parser.add_argument("--skip-dpmes", action="store_true", help="Only sync time-series indicators.")
        parser.add_argument("--year", type=int, help="Ethiopian year for DPMES lookups (default: last completed).")

    def handle(self, *args, **options):
        period = {"year": options["year"]} if options["year"] else None
        try:
            counts = sync(include_dpmes=not options["skip_dpmes"], period=period, log=self.stdout.write)
        except (dpmes2.DPMES2Error, LLMError, OSError, ValueError) as exc:
            raise CommandError(f"Catalog sync failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            "Catalog synced: " + ", ".join(f"{count} {name}" for name, count in counts.items())
        ))
