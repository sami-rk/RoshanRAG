"""Recover documents and questions left stuck in an in-progress status.

Background indexing/answering runs in daemon threads. If a worker is killed or
restarted mid-task (e.g. container restart, deploy, OOM), the item is left in
``pending``/``generating`` forever. This command marks such items as ``failed``
with a clear message so they can be retried from the admin.

Run automatically on container startup (see ``entrypoint.sh``) or manually:

    python manage.py recover_stuck_tasks [--minutes 30]
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import Document
from qa.models import Question

DEFAULT_STUCK_AFTER_MINUTES = 30


class Command(BaseCommand):
    help = "Marks documents/questions stuck in pending/generating as failed"

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=DEFAULT_STUCK_AFTER_MINUTES,
            help="Age (in minutes) after which an in-progress item is considered stuck",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options["minutes"])

        document_count = Document.objects.filter(
            status=Document.Status.PENDING,
            updated_at__lt=cutoff,
        ).update(
            status=Document.Status.FAILED,
            error_message="ایندکس‌سازی ناتمام ماند؛ از «ایندکس‌سازی مجدد» استفاده کنید",
        )

        question_count = Question.objects.filter(
            status__in=[Question.Status.PENDING, Question.Status.GENERATING],
            created_at__lt=cutoff,
        ).update(
            status=Question.Status.FAILED,
            error_message="پاسخ‌دهی ناتمام ماند؛ از «پاسخ‌دهی مجدد» استفاده کنید",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Recovered {document_count} stuck document(s) and "
                f"{question_count} stuck question(s)"
            )
        )
