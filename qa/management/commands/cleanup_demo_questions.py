"""Remove expired anonymous demo questions.

Demo questions are created via ``/api/questions/demo_ask/`` with ``user=None``
and a ``demo_token``. They are never scoped to an owner and would
accumulate forever. This command deletes demo rows older than a threshold
(default 7 days).

Run manually or via a cron job:

    python manage.py cleanup_demo_questions [--days 7] [--dry-run]
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from qa.models import Question

DEFAULT_DAYS = 7


class Command(BaseCommand):
    help = "Deletes expired anonymous demo questions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_DAYS,
            help="Age (in days) after which a demo question is considered expired",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only count; do not delete",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        queryset = Question.objects.filter(
            user__isnull=True,
            demo_token__isnull=False,
            created_at__lt=cutoff,
        )
        count = queryset.count()
        if options["dry_run"]:
            self.stdout.write(f"Would delete {count} expired demo question(s) (dry run)")
            return
        deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired demo question(s)"))
