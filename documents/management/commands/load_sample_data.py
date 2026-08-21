from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save

from documents import signals as documents_signals
from documents.models import Document
from documents.services.indexing import index_document

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_data"
SUPPORTED = {".docx", ".pdf", ".txt"}


class Command(BaseCommand):
    help = "Loads the bundled sample documents into the system"

    def handle(self, *args, **options):
        if not SAMPLE_DIR.exists():
            self.stderr.write(f"Sample data directory not found: {SAMPLE_DIR}")
            return

        post_save.disconnect(documents_signals.on_document_saved, sender=Document)
        try:
            count = 0
            for path in sorted(SAMPLE_DIR.iterdir()):
                if path.suffix.lower() not in SUPPORTED:
                    continue
                title = path.stem
                if Document.objects.filter(title=title).exists():
                    self.stdout.write(f"Skipped existing: {title}")
                    continue
                document = Document.objects.create(
                    title=title,
                    file=File(path.open("rb"), name=path.name),
                )
                index_document(document.pk)
                count += 1
                self.stdout.write(self.style.SUCCESS(f"Loaded: {title}"))
        finally:
            post_save.connect(documents_signals.on_document_saved, sender=Document)

        self.stdout.write(self.style.SUCCESS(f"Loaded {count} sample documents"))