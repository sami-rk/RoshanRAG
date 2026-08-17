import logging

from core.chroma_client import (
    delete_document_chunks,
    get_chroma_vectorstore,
)
from core.workers import run_in_background
from documents.models import Document

from .chunking import split_text
from .extraction import extract_text

logger = logging.getLogger(__name__)


def index_document(document_id: int) -> None:
    document = Document.objects.filter(pk=document_id).first()
    if document is None:
        return
    try:
        text = extract_text(document.file.path, document.file_extension)
        if not text:
            raise ValueError("متن استخراج‌شده از سند خالی است")

        chunks = split_text(text)
        if not chunks:
            raise ValueError("سند هیچ بخش قابل بازیابی تولید نکرد")

        ids = [f"doc-{document.pk}-{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "document_id": document.pk,
                "title": document.title,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]

        delete_document_chunks(document.pk)
        get_chroma_vectorstore().add_texts(
            texts=chunks,
            metadatas=metadatas,
            ids=ids,
        )

        document.full_text = text
        document.status = Document.Status.READY
        document.error_message = ""
    except Exception as exc:
        document.status = Document.Status.FAILED
        document.error_message = str(exc)
        logger.exception("Failed to index document %s", document_id)

    # The document may have been deleted while indexing was in flight.
    if Document.objects.filter(pk=document.pk).exists():
        document.save(update_fields=["full_text", "status", "error_message", "updated_at"])


def schedule_index(document_id: int) -> None:
    run_in_background(index_document, document_id)