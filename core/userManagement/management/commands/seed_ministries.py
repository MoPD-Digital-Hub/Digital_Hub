import requests
from django.core.management.base import BaseCommand, CommandError

from userManagement.models import CustomUser, Ministry, default_ministry


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

        self._link_dpmes2()

        # Every user belongs to an organization; default the unassigned to MoPD.
        mopd_id = default_ministry()
        if mopd_id is None:
            self.stdout.write(self.style.WARNING("MoPD not found — users without a ministry were left as-is."))
            return
        backfilled = CustomUser.objects.filter(ministry__isnull=True).update(ministry_id=mopd_id)
        if backfilled:
            self.stdout.write(self.style.SUCCESS(f"Assigned MoPD to {backfilled} user(s) without an organization."))

    def _link_dpmes2(self):
        """Store each ministry's DPMES2 organization id, matched by code
        (DPMES2 ids differ from DPMES1's external_id)."""
        from dashboard import dpmes2

        if not dpmes2.is_configured():
            self.stdout.write(self.style.WARNING("DPMES2_API_KEY not set — skipped DPMES2 linking."))
            return
        try:
            organizations = dpmes2.child_organizations()
        except dpmes2.DPMES2Error as exc:
            self.stdout.write(self.style.WARNING(f"DPMES2 linking skipped: {exc}"))
            return

        by_code = {str(org.get("code", "")).upper(): org["id"] for org in organizations if org.get("code")}
        linked = unmatched = 0
        for ministry in Ministry.objects.all():
            org_id = by_code.get(ministry.abbreviation.upper())
            if org_id is None:
                unmatched += 1
                continue
            if ministry.dpmes2_id != org_id:
                ministry.dpmes2_id = org_id
                ministry.save(update_fields=["dpmes2_id"])
            linked += 1
        self.stdout.write(self.style.SUCCESS(f"DPMES2 linked: {linked} ministries, {unmatched} without a matching code."))
