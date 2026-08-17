from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.serializers import DocumentSerializer

User = get_user_model()


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
        file = SimpleUploadedFile("my-doc.docx", b"x", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        serializer = DocumentSerializer(data={"file": file})
        self.assertTrue(serializer.is_valid(), serializer.errors)
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
        from unittest.mock import patch

        file = SimpleUploadedFile("note.txt", b"hello world", content_type="text/plain")
        with patch("documents.signals.schedule_index"):
            response = self.client.post("/api/documents/", {"file": file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.status, Document.Status.PENDING)
        self.assertEqual(document.title, "note")

    def test_q_filter_searches_title(self):
        Document.objects.create(title="گزارش فروش", file="documents/x.txt", status=Document.Status.READY)
        response = self.client.get("/api/documents/?q=فروش")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)