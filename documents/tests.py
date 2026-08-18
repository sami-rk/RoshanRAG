import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
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


MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 72 720 Td (Hello PDF world) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


def _minimal_docx_bytes() -> bytes:
    """Return the bytes of a structurally plausible DOCX (a ZIP container)."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


class DocumentSerializerTests(APITestCase):
    def test_supported_extensions_accepted(self):
        file = SimpleUploadedFile("readme.txt", b"content", content_type="text/plain")
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_pdf_extension_accepted(self):
        file = SimpleUploadedFile(
            "readme.pdf", MINIMAL_PDF, content_type="application/pdf"
        )
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_unsupported_extension_rejected(self):
        file = SimpleUploadedFile("readme.csv", b"a,b", content_type="text/csv")
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
            _minimal_docx_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with patch("documents.signals.schedule_index"):
            document = serializer.save()
        self.assertEqual(document.title, "my-doc")

    def test_file_content_must_match_the_extension(self):
        cases = [
            ("renamed.pdf", b"this is actually plain text"),
            ("renamed.docx", b"not a zip container"),
            ("renamed.txt", b"binary\x00\x01\x02content"),
        ]
        for name, content in cases:
            with self.subTest(name=name):
                file = SimpleUploadedFile(name, content)
                serializer = DocumentSerializer(data={"file": file})
                self.assertFalse(serializer.is_valid())
                self.assertIn("file", serializer.errors)

    def test_content_matching_the_extension_is_accepted(self):
        pdf = SimpleUploadedFile("ok.pdf", MINIMAL_PDF)
        self.assertTrue(DocumentSerializer(data={"file": pdf}).is_valid())
        docx = SimpleUploadedFile("ok.docx", _minimal_docx_bytes())
        self.assertTrue(DocumentSerializer(data={"file": docx}).is_valid())


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

    def test_status_filter(self):
        with patch("documents.signals.schedule_index"):
            Document.objects.create(
                title="آماده", file="documents/a.txt", status=Document.Status.READY
            )
            Document.objects.create(
                title="در انتظار", file="documents/b.txt", status=Document.Status.PENDING
            )
        response = self.client.get("/api/documents/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_batch_upload_creates_all_valid_files(self):
        first = SimpleUploadedFile("one.txt", b"content one", content_type="text/plain")
        second = SimpleUploadedFile("two.txt", b"content two", content_type="text/plain")
        with patch("documents.signals.schedule_index") as schedule:
            response = self.client.post(
                "/api/documents/batch/",
                {"files": [first, second]},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["created"]), 2)
        self.assertEqual(len(response.data["errors"]), 0)
        self.assertEqual(Document.objects.count(), 2)
        self.assertEqual(schedule.call_count, 2)

    def test_batch_upload_without_files_is_rejected(self):
        response = self.client.post(
            "/api/documents/batch/", {}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_upload_reports_invalid_files(self):
        valid = SimpleUploadedFile("ok.txt", b"content", content_type="text/plain")
        invalid = SimpleUploadedFile(
            "bad.csv", b"a,b", content_type="text/csv"
        )
        with patch("documents.signals.schedule_index"):
            response = self.client.post(
                "/api/documents/batch/",
                {"files": [valid, invalid]},
                format="multipart",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["created"]), 1)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertEqual(response.data["errors"][0]["file"], "bad.csv")


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
        doc = _make_document("file.csv", b"a,b")
        with (
            patch("documents.services.indexing.get_chroma_vectorstore"),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.FAILED)
        self.assertIn("پشتیبانی", doc.error_message)
        self.assertEqual(doc.full_text, "")

    def test_index_pdf_document_success(self):
        doc = _make_document("report.pdf", MINIMAL_PDF)
        vectorstore = MagicMock()
        with (
            patch("documents.services.indexing.get_chroma_vectorstore", return_value=vectorstore),
            patch("documents.services.indexing.delete_document_chunks"),
        ):
            index_document(doc.pk)

        doc.refresh_from_db()
        self.assertEqual(doc.status, Document.Status.READY)
        self.assertIn("Hello PDF world", doc.full_text)
        self.assertEqual(doc.error_message, "")

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


class DocumentAdminFormTests(TestCase):
    def test_admin_form_rejects_unsupported_extension(self):
        from documents.forms import DocumentAdminForm

        file = SimpleUploadedFile("readme.csv", b"a,b", content_type="text/csv")
        form = DocumentAdminForm(data={"title": "سند"}, files={"file": file})
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)

    def test_admin_form_accepts_pdf(self):
        from documents.forms import DocumentAdminForm

        file = SimpleUploadedFile(
            "readme.pdf", MINIMAL_PDF, content_type="application/pdf"
        )
        form = DocumentAdminForm(
            data={"title": "سند", "status": Document.Status.PENDING}, files={"file": file}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_form_rejects_oversized_file(self):
        from documents.forms import DocumentAdminForm

        with override_settings(MAX_UPLOAD_SIZE_MB=0):
            file = SimpleUploadedFile("big.txt", b"x" * 100, content_type="text/plain")
            form = DocumentAdminForm(data={"title": "سند"}, files={"file": file})
            self.assertFalse(form.is_valid())
            self.assertIn("file", form.errors)

    def test_admin_form_accepts_supported_extension(self):
        from documents.forms import DocumentAdminForm

        file = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        form = DocumentAdminForm(
            data={"title": "سند", "status": Document.Status.PENDING}, files={"file": file}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_form_rejects_mismatched_content(self):
        from documents.forms import DocumentAdminForm

        file = SimpleUploadedFile("note.pdf", b"not a pdf", content_type="application/pdf")
        form = DocumentAdminForm(
            data={"title": "سند", "status": Document.Status.PENDING}, files={"file": file}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("file", form.errors)


class DocumentSignalsTests(TestCase):
    def test_creating_document_does_not_leak_none_key(self):
        from documents import signals as signals_module

        _make_document("note.txt", "متن".encode("utf-8"))
        self.assertNotIn(None, signals_module._old_files)

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

    def test_deleting_document_removes_stored_file(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            doc = _make_document("work.txt", "متن".encode("utf-8"))
            stored_path = doc.file.path
            self.assertTrue(Path(stored_path).exists())
            with patch("core.chroma_client.delete_document_chunks"):
                doc.delete()
            self.assertFalse(Path(stored_path).exists())


class LoadSampleDataCommandTests(TestCase):
    SAMPLE_TITLES = {
        "دستورالعمل-استخدام",
        "سوالات-متداول",
        "سیاست-حریم-خصوصی",
        "گزارش-فروش-سه-ماهه-اول-1403",
    }

    def test_loads_all_sample_documents(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            with patch("documents.management.commands.load_sample_data.index_document") as index:
                call_command("load_sample_data")
            titles = set(Document.objects.values_list("title", flat=True))
            self.assertEqual(titles, self.SAMPLE_TITLES)
            self.assertEqual(index.call_count, 4)

    def test_second_run_skips_existing(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            with patch("documents.management.commands.load_sample_data.index_document") as index:
                call_command("load_sample_data")
                call_command("load_sample_data")
            self.assertEqual(Document.objects.count(), 4)
            self.assertEqual(index.call_count, 4)

    def test_post_save_signal_is_reconnected(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            call_command("load_sample_data")
            with patch("documents.signals.schedule_index") as schedule:
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "extra.txt"
                    path.write_bytes("متن".encode("utf-8"))
                    Document.objects.create(
                        title="extra", file=File(path.open("rb"), name="extra.txt")
                    )
                schedule.assert_called_once()


class DocumentAdminActionTests(TestCase):
    def _admin_request(self):
        request = RequestFactory().get("/")
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_retry_indexing_schedules_failed_documents(self):
        from core.admin_site import roshan_admin_site
        from documents.admin import DocumentAdmin

        doc = _make_document("broken.txt", b"")
        Document.objects.filter(pk=doc.pk).update(status=Document.Status.FAILED)
        with patch("documents.admin.schedule_index") as schedule:
            DocumentAdmin(Document, roshan_admin_site).retry_indexing(
                self._admin_request(), Document.objects.filter(pk=doc.pk)
            )
        schedule.assert_called_once_with(doc.pk)

    def test_retry_indexing_shows_a_success_message(self):
        from core.admin_site import roshan_admin_site
        from documents.admin import DocumentAdmin

        doc = _make_document("broken.txt", b"")
        request = self._admin_request()
        with patch("documents.admin.schedule_index"):
            DocumentAdmin(Document, roshan_admin_site).retry_indexing(
                request, Document.objects.filter(pk=doc.pk)
            )
        self.assertEqual(len(request._messages), 1)


class DocumentUploadAdminTests(TestCase):
    def test_upload_page_requires_staff(self):
        response = self.client.get("/admin/documents/document/upload/")
        self.assertEqual(response.status_code, 302)

    def test_upload_page_renders_for_staff(self):
        user = get_user_model().objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.client.force_login(user)
        response = self.client.get("/admin/documents/document/upload/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dropzone")
        self.assertContains(response, "document-upload.js")

    def test_batch_upload_link_on_changelist(self):
        user = get_user_model().objects.create_user(
            username="staff", password="pass", is_staff=True, is_superuser=True
        )
        self.client.force_login(user)
        response = self.client.get("/admin/documents/document/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/admin/documents/document/upload/")


class ScheduleIndexTests(TestCase):
    def test_marks_document_failed_when_worker_dies(self):
        from documents.services.indexing import schedule_index

        with patch("documents.signals.schedule_index"):
            document = Document.objects.create(
                title="سند", file="documents/x.txt"
            )
        with patch("documents.services.indexing.run_in_background") as run:
            schedule_index(document.pk)
        on_error = run.call_args.kwargs["on_error"]
        on_error(RuntimeError("kaboom"))
        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertEqual(document.error_message, "kaboom")

    def test_ignores_deleted_document(self):
        from documents.services.indexing import schedule_index

        with patch("documents.signals.schedule_index"):
            document = Document.objects.create(
                title="سند", file="documents/x.txt"
            )
        with patch("documents.services.indexing.run_in_background") as run:
            schedule_index(document.pk)
        document.delete()
        run.call_args.kwargs["on_error"](RuntimeError("kaboom"))
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
