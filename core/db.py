from django.db.backends.signals import connection_created

BUSY_TIMEOUT_MS = 5000


def _enable_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")
    cursor.close()


connection_created.connect(_enable_sqlite_pragmas, dispatch_uid="roshan_sqlite_pragmas")