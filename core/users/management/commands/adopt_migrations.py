"""Switch an existing database to the migrations committed in the repository.

Migrations used to be generated on each machine and never committed, so a
database's migration history (the django_migrations table) names files that no
longer exist. This command rewrites that history for the project's apps to the
committed *baseline* migrations (the schema as it was when migrations were
first committed), without touching any table, after checking that every table
and column of that baseline is already there. Migrations added after the
baseline are left for `migrate` to apply as usual.

    python manage.py adopt_migrations            # report only
    python manage.py adopt_migrations --check    # exit 1 if adoption is needed (deploy.sh)
    python manage.py adopt_migrations --apply    # rewrite the history (back up first)
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

# The migrations that describe the schema every pre-existing database already
# has, by app label. Never add later migrations here: they must really run.
BASELINE = {
    "AI": ("0001_initial", "0002_initial"),
    "Notification": ("0001_initial", "0002_initial"),
    "userManagement": ("0001_initial",),
    "chat": ("0001_initial", "0002_initial"),
    "mobile": ("0001_initial",),
}
BASELINE_KEYS = {(app, name) for app, names in BASELINE.items() for name in names}


def needs_adoption(applied, on_disk):
    """True when the recorded history cannot be continued by a plain `migrate`."""
    if not applied:
        return False                      # a new database: migrate creates everything
    stale = applied - on_disk             # names from the old, uncommitted files
    return bool(stale) or not BASELINE_KEYS <= applied


def schema_problems(loader):
    """Tables or columns of the baseline schema that the database lacks."""
    state = loader.project_state([(app, names[-1]) for app, names in BASELINE.items()])
    problems = []
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        for model in state.apps.get_models(include_auto_created=True):
            meta = model._meta
            if meta.app_label not in BASELINE or not meta.managed or meta.proxy:
                continue
            if meta.db_table not in tables:
                problems.append(f"missing table {meta.db_table}")
                continue
            columns = {c.name for c in connection.introspection.get_table_description(cursor, meta.db_table)}
            for field in meta.local_concrete_fields:
                if field.column not in columns:
                    problems.append(f"missing column {meta.db_table}.{field.column}")
    return problems


class Command(BaseCommand):
    help = "Rewrite the project apps' migration history to the committed baseline (schema checked first)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Rewrite the history (otherwise only report).")
        parser.add_argument("--check", action="store_true", help="Exit with an error if adoption is needed.")

    def handle(self, *args, apply=False, check=False, **options):
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        applied = {key for key in recorder.applied_migrations() if key[0] in BASELINE}
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        on_disk = {key for key in loader.disk_migrations if key[0] in BASELINE}

        if not needs_adoption(applied, on_disk):
            self.stdout.write(self.style.SUCCESS("Migration history matches the committed migrations."))
            return

        stale, missing = sorted(applied - on_disk), sorted(BASELINE_KEYS - applied)
        self.stdout.write(f"Recorded but not in the repository: {', '.join(f'{a}.{n}' for a, n in stale) or 'none'}")
        self.stdout.write(f"Baseline migrations not recorded: {', '.join(f'{a}.{n}' for a, n in missing) or 'none'}")
        if check:
            raise CommandError("The migration history needs adopting: run `manage.py adopt_migrations --apply` "
                               "once, after a database backup (docs/deploy.md).")

        problems = schema_problems(loader)
        if problems:
            raise CommandError("The database does not match the baseline schema, so the history was not changed:\n  "
                               + "\n  ".join(problems))
        self.stdout.write("Schema check: every table and column of the baseline schema is present.")
        if not apply:
            self.stdout.write("Nothing changed. Run again with --apply to rewrite the history.")
            return

        with transaction.atomic():
            recorder.migration_qs.filter(app__in=BASELINE).delete()
            for app_label, name in sorted(BASELINE_KEYS):
                recorder.record_applied(app_label, name)
        later = sorted(on_disk - BASELINE_KEYS)
        self.stdout.write(self.style.SUCCESS(
            f"Adopted the {len(BASELINE_KEYS)} baseline migrations; no tables were changed."))
        if later:
            self.stdout.write(f"`migrate` will now apply: {', '.join(f'{a}.{n}' for a, n in later)}")
