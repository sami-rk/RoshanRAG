import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def run_in_background(func, *args, **kwargs):
    def wrapper():
        close_old_connections()
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("Background task failed: %s", func.__name__)
        finally:
            close_old_connections()

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread