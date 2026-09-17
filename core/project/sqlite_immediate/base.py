"""SQLite backend that opens transactions with BEGIN IMMEDIATE.

Django's default deferred BEGIN lets a transaction start as a reader and
upgrade to a writer mid-transaction (e.g. update_or_create's SELECT then
UPDATE). When two requests do that concurrently, SQLite raises "database
is locked" immediately — the busy timeout cannot help with a mid-
transaction upgrade. Acquiring the write lock at BEGIN makes concurrent
writers queue on the busy timeout instead. Dev/SQLite only; production
runs PostgreSQL. (Django 5.1+ replaces this with the "transaction_mode"
option.)
"""

from django.db.backends.sqlite3 import base


class DatabaseWrapper(base.DatabaseWrapper):
    def _start_transaction_under_autocommit(self):
        self.cursor().execute("BEGIN IMMEDIATE")
