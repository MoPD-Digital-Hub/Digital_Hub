"""Switch an existing database to the migrations committed in the repository.

Migrations used to be generated on each machine and never committed, so a
database's migration history (the django_migrations table) names files that no
longer exist. This command rewrites that history for the project's apps to the
committed files, without touching any table, after checking that every table
and column the models need is already there.

    python manage.py adopt_migrations            # report only
    python manage.py adopt_migrations --check    # exit 1 if adoption is needed (deploy.sh)
    python manage.py adopt_migrations --apply    # rewrite the history (back up first)
"""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

# App labels whose migrations live in this repository.
PROJECT_APPS = ("AI", "Notification", "userManagement", "chat", "mobile")


def schema_problems():
    """Tables or columns the current models expect but the database lacks."""
    problems = []
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        for label in PROJECT_APPS:
            for model in apps.get_app_config(label).get_models(include_auto_created=True):
                meta = model._meta
                if not meta.managed or meta.proxy:
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
    help = "Rewrite the project apps' migration history to the committed migrations (schema checked first)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Rewrite the history (otherwise only report).")
        parser.add_argument("--check", action="store_true", help="Exit with an error if adoption is needed.")

    def handle(self, *args, apply=False, check=False, **options):
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        applied = {key for key in recorder.applied_migrations() if key[0] in PROJECT_APPS}
        on_disk = {key for key in MigrationLoader(connection, ignore_no_migrations=True).disk_migrations
                   if key[0] in PROJECT_APPS}

        if not applied or applied == on_disk:
            # A new database, or one already on the committed migrations: `migrate` handles it.
            self.stdout.write(self.style.SUCCESS("Migration history matches the committed migrations."))
            return

        stale, missing = sorted(applied - on_disk), sorted(on_disk - applied)
        self.stdout.write(f"Recorded but not in the repository: {', '.join(f'{a}.{n}' for a, n in stale) or 'none'}")
        self.stdout.write(f"In the repository but not recorded: {', '.join(f'{a}.{n}' for a, n in missing) or 'none'}")
        if check:
            raise CommandError("The migration history needs adopting: run `manage.py adopt_migrations --apply` "
                               "once, after a database backup (docs/deploy.md).")

        problems = schema_problems()
        if problems:
            raise CommandError("The database does not match the models, so the history was not changed:\n  "
                               + "\n  ".join(problems))
        self.stdout.write("Schema check: every table and column the models need is present.")
        if not apply:
            self.stdout.write("Nothing changed. Run again with --apply to rewrite the history.")
            return

        with transaction.atomic():
            recorder.migration_qs.filter(app__in=PROJECT_APPS).delete()
            for app_label, name in sorted(on_disk):
                recorder.record_applied(app_label, name)
        self.stdout.write(self.style.SUCCESS(
            f"Adopted {len(on_disk)} committed migrations for {', '.join(PROJECT_APPS)}; no tables were changed."))
