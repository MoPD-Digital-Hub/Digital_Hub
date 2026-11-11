from django.core.management.base import BaseCommand, CommandError

from ai.engine.catalog import sync
from ai.engine.llm import LLMError
from integrations.dpmes import client as dpmes_client


class Command(BaseCommand):
    help = (
        "Sync the entity catalog (indicators, organizations, policy areas, goals, SDG goals and "
        "indicators) from the time-series and DPMES APIs and the national SDG platform, and embed "
        "new or changed entries. Safe to run repeatedly; "
        "schedule it daily so new indicators become answerable."
    )

    def add_arguments(self, parser):
        parser.add_argument("--skip-dpmes", action="store_true", help="Leave DPMES entries as they are.")
        parser.add_argument("--skip-sdg", action="store_true", help="Leave SDG entries as they are.")
        parser.add_argument("--year", type=int, help="Ethiopian year for DPMES lookups (default: last completed).")

    def handle(self, *args, **options):
        period = {"year": options["year"]} if options["year"] else None
        try:
            counts = sync(include_dpmes=not options["skip_dpmes"], include_sdg=not options["skip_sdg"],
                          period=period, log=self.stdout.write)
        except (dpmes_client.DPMES2Error, LLMError, OSError, ValueError) as exc:
            raise CommandError(f"Catalog sync failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(
            "Catalog synced: " + ", ".join(f"{count} {name}" for name, count in counts.items())
        ))
