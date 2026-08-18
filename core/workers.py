import logging
import threading
import time

from django.db import OperationalError, close_old_connections

logger = logging.getLogger(__name__)


def _is_database_lock(exc: Exception) -> bool:
    return (
        isinstance(exc, OperationalError)
        and "database table is locked" in str(exc).lower()
    )


def run_in_background(
    func,
    *args,
    on_error=None,
    retries=3,
    backoff_seconds=0.5,
    **kwargs,
):
    """Run ``func(*args, **kwargs)`` on a daemon thread.

    SQLite can briefly lock a table while another writer is mid-transaction;
    those failures are retried with backoff instead of silently dropping the
    task. Any other exception (or a lock that keeps failing) is logged and
    passed to ``on_error(exc)``, which lets the caller mark the affected
    object as failed so the item is not left stuck in an in-progress status.
    """

    def wrapper():
        close_old_connections()
        try:
            attempt = 0
            while True:
                try:
                    func(*args, **kwargs)
                    return
                except Exception as exc:
                    if _is_database_lock(exc) and attempt < retries:
                        attempt += 1
                        time.sleep(backoff_seconds * attempt)
                        close_old_connections()
                        continue
                    raise
        except Exception as exc:
            logger.exception("Background task failed: %s", func.__name__)
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:
                    logger.exception(
                        "Background error handler failed for %s", func.__name__
                    )
        finally:
            close_old_connections()

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread