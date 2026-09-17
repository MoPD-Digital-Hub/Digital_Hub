import requests
from django.core.management.base import BaseCommand, CommandError

from userManagement.models import Ministry


class Command(BaseCommand):
    help = "Seed/refresh the Ministry (organization) table from the DPMES all-ministries API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="https://dpmes.mopd.gov.et/api/digital-hub/all-ministries/",
            help="DPMES all-ministries endpoint.",
        )

    def handle(self, *args, **options):
        try:
            response = requests.get(options["url"], timeout=20)
            response.raise_for_status()
            payload = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise CommandError(f"Failed to fetch ministries from DPMES: {exc}")

        ministries = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(ministries, list):
            raise CommandError("Unexpected DPMES response shape: no 'data' list.")

        created = updated = skipped = 0
        for item in ministries:
            external_id = item.get("id")
            name = (item.get("responsible_ministry_eng") or "").strip()
            if external_id is None or not name:
                skipped += 1
                continue

            fields = {
                "name": name,
                "name_am": (item.get("responsible_ministry_amh") or "").strip(),
                "abbreviation": (item.get("code") or "").strip(),
                "image": item.get("image") or "",
                "is_active": bool(item.get("ministry_is_visable", True)),
            }

            # Match by DPMES id first; adopt an existing same-named row that
            # was created manually before seeding.
            ministry = (
                Ministry.objects.filter(external_id=external_id).first()
                or Ministry.objects.filter(name=name).first()
            )
            if ministry is None:
                Ministry.objects.create(external_id=external_id, **fields)
                created += 1
            else:
                ministry.external_id = external_id
                for attr, value in fields.items():
                    setattr(ministry, attr, value)
                ministry.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Ministries seeded: {created} created, {updated} updated, {skipped} skipped."
        ))
