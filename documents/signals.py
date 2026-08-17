import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Document
from .services.indexing import schedule_index

logger = logging.getLogger(__name__)

_old_files = {}


@receiver(pre_save, sender=Document)
def remember_old_file(sender, instance, **kwargs):
    if instance.pk:
        try:
            _old_files[instance.pk] = Document.objects.get(pk=instance.pk).file.name
        except Document.DoesNotExist:
            _old_files[instance.pk] = None
    else:
        _old_files[instance.pk] = None


@receiver(post_save, sender=Document)
def on_document_saved(sender, instance, created, **kwargs):
    old = _old_files.pop(instance.pk, None)
    new = instance.file.name if instance.file else None
    if created or old != new:
        if old and old != new:
            instance.file.storage.delete(old)
        if new:
            schedule_index(instance.pk)


@receiver(post_delete, sender=Document)
def on_document_deleted(sender, instance, **kwargs):
    from core.chroma_client import delete_document_chunks

    try:
        delete_document_chunks(instance.pk)
    except Exception:
        # Chroma might be unreachable or have lost the collection. The row is
        # already gone from the database, so do not fail the deletion; the
        # orphaned chunks will be replaced the next time the document is
        # re-uploaded (indexing deletes leftovers before adding new ones).
        logger.exception("Failed to remove vector chunks for document %s", instance.pk)