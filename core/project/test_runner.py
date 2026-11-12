"""The test runner: Django's, plus a clean end on PostgreSQL.

Database work done on worker threads (WebSocket consumers, sync_to_async,
asyncio.to_thread) can leave a session open when the tests finish. PostgreSQL
then refuses to drop the test database ("is being accessed by other users") and
the run fails although every test passed. Before dropping it, end those
leftover sessions.
"""

from django.db import connections
from django.test.runner import DiscoverRunner


class Runner(DiscoverRunner):
    def teardown_databases(self, old_config, **kwargs):
        for connection in connections.all():
            if connection.vendor != "postgresql":
                continue
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
                )
        super().teardown_databases(old_config, **kwargs)
