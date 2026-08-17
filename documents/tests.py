import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.serializers import DocumentSerializer
from documents.services.indexing import index_document

User = get_user_model()


def _make_document(name: str, content: bytes) -> Document:
    """Create a Document whose file exists on disk (needed for indexing).

    The post_save signal is patched so no real background indexing thread
    (which would touch Chroma) is spawned during tests.
    """
    with patch("documents.signals.schedule_index"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_bytes(content)
            return Document.objects.create(
                title=Path(name).stem,
                file=File(path.open("rb"), name=name),
            )


class DocumentSerializerTests(APITestCase):
    def test_supported_extensions_accepted(self):
        file = SimpleUploadedFile("readme.txt", b"content", content_type="text/plain")
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_unsupported_extension_rejected(self):
        file = SimpleUploadedFile("readme.pdf", b"%PDF-1.4", content_type="application/pdf")
        serializer = DocumentSerializer(data={"file": file})
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    @override_settings(MAX_UPLOAD_SIZE_MB=0)
    def test_oversized_file_rejected(self):
        file = SimpleUploadedFile("big.txt", b"x" * 100, content_type="text/plain")
        serializer = DocumentSerializer(data={"file": file})
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    def test_title_defaults_to_filename_stem(self):
        file = SimpleUploadedFile(
            "my-doc.docx",
            b"x",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with patch("documents.signals.schedule_index"):
            document = serializer.save()
        self.assertEqual(document.title, "my-doc")


class DocumentAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client.force_authenticate(user=self.user)

    def test_list_requires_authentication(self):
        anonymous = self.client_class()
        response = anonymous.get("/api/documents/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_is_empty(self):
        response = self.client.get("/api/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_create_document_sets_pending(self):
        file = SimpleUploadedFile("note.txt", b"hello world", content_type="text/plain")
        with patch("documents.signals.schedule_index"):
            response = self.client.post("/api/documents/", {"file": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.status, Document.Status.PENDING)
        self.assertEqual(document.title, "note")

    def test_q_filter_searches_title(self):
        with patch("documents.signals.schedule_index"):
            Document.objects.create(
                title="گزارش فروش", file="documents/x.txt", status=Document.Status.READY
            )
        response = self.client.get("/api/documents/?q=فروش")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_q_filter_searches_full_text(self):
        with patch("documents.signals.schedule_index"):
            Document.objects.create(
                title="سند الف",
                file="documents/x.txt",
                full_text="محتوای کاملاً منحصربه‌فرد xyz123",
                status=Document.Status.READY,
            )
        response = self.client.get("/api/documents/?q=xyz123")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class IndexingServiceTests(TestCase):
    def test_index_txt_document_success(self):
        doc = _make_document("note.txt", "متن سند آزمایشی برای ایندکس‌گذاری".encode("utf-8"))
        vectorstore = MagicMock()
        with (
            patch("documents.services.indexing.get_chroma_vectorstore", return_value=vectorstore),
            patch("documents.services.indexing.delete_document_chunks") as delete_chunks,
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertIn("متن سند آزمایشی", doc.full_text)
        self.assertEqual(doc.error_message, "")
        delete_chunks.assert_called_once_with(doc.pk)

    def test_index_document_adds_chunks_to_vectorstore(self):
        doc = _make_document("note.txt", "قسمت اول متن. ".encode("utf-8") * 60)
        vectorstore = MagicMock()
        with (
            patch("documents.services.indexing.get_chroma_vectorstore", return_value=vectorstore),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.READY)
        call_kwargs = vectorstore.add_texts.call_args.kwargs
        self.assertIn("texts", call_kwargs)
        self.assertIn("ids", call_kwargs)
        self.assertIn("metadatas", call_kwargs)
        self.assertEqual(len(call_kwargs["texts"]), len(call_kwargs["ids"]))
        for metadata in call_kwargs["metadatas"]:
            self.assertEqual(metadata["document_id"], doc.pk)

    def test_index_unsupported_extension_sets_failed(self):
        doc = _make_document("file.pdf", b"%PDF-1.4 fake content")
        with (
            patch("documents.services.indexing.get_chroma_vectorstore"),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("پشتیبانی", doc.error_message)
        self.assertEqual(doc.full_text, "")

    def test_index_empty_text_sets_failed(self):
        doc = _make_document("empty.txt", b"")
        with (
            patch("documents.services.indexing.get_chroma_vectorstore"),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("خالی", doc.error_message)

    def test_index_missing_document_is_noop(self):
        with (
            patch("documents.services.indexing.get_chroma_vectorstore") as vectorstore,
            patch("documents.services.indexing.delete_document_chunks") as delete_chunks,
        ):
            index_document(99999)
        vectorstore.assert_not_called()
        delete_chunks.assert_not_called()

    def test_deleted_document_mid_index_does_not_crash(self):
        doc = _make_document("note.txt", "متن سند".encode("utf-8"))

        def delete_then_return(*args, **kwargs):
            Document.objects.filter(pk=doc.pk).delete()
            return MagicMock()

        with (
            patch(
                "documents.services.indexing.get_chroma_vectorstore",
                side_effect=delete_then_return,
            ),
            patch("documents.services.indexing.delete_document_chunks"),
            # The in-flight delete fires the post_delete signal, which calls the
            # real chroma cleanup — patch it so tests stay hermetic.
            patch("core.chroma_client.delete_document_chunks"),
        ):
            # Must not raise even though the row vanished mid-index
            index_document(doc.pk)
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())


class DocumentSignalsTests(TestCase):
    def test_replacing_file_deletes_old_file_and_reindexes(self):
        doc = _make_document("first.txt", "نسخه اول".encode("utf-8"))
        old_path = doc.file.path

        with (
            patch("documents.services.indexing.get_chroma_vectorstore"),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)  # make it ready first
        doc.refresh_from_db()
        self.assertTrue(Path(old_path).exists())

        # Replace the file: the old file must be deleted and re-index scheduled
        with tempfile.TemporaryDirectory() as tmp:
            new_path = Path(tmp) / "second.txt"
            new_path.write_text("نسخه دوم", encoding="utf-8")
            with patch("documents.signals.schedule_index") as schedule:
                doc.file = File(new_path.open("rb"), name="second.txt")
                doc.save()
            self.assertFalse(Path(old_path).exists())
            schedule.assert_called_once_with(doc.pk)

    def test_deleting_document_removes_chunks(self):
        doc = _make_document("note.txt", "متن".encode("utf-8"))
        pk = doc.pk
        with patch("core.chroma_client.delete_document_chunks") as delete_chunks:
            doc.delete()
        delete_chunks.assert_called_once_with(pk)

    def test_deleting_document_tolerates_chroma_outage(self):
        doc = _make_document("note.txt", "متن".encode("utf-8"))
        with patch(
            "core.chroma_client.delete_document_chunks",
            side_effect=RuntimeError("chroma unreachable"),
        ):
            doc.delete()
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())
