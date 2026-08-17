from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from documents.models import Document
from qa.models import Question


class HealthCheckTests(TestCase):
    def test_health_ok_when_dependencies_available(self):
        with patch("core.chroma_client._get_client") as client:
            client.return_value.heartbeat.return_value = 1
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_503_when_chroma_unavailable(self):
        with patch("core.chroma_client._get_client") as client:
            client.return_value.heartbeat.side_effect = ConnectionError("down")
            response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["chroma"], "unreachable")
        self.assertEqual(response.json()["database"], "ok")

    def test_health_503_when_database_unavailable(self):
        with patch("core.views.connection") as connection:
            connection.ensure_connection.side_effect = Exception("db down")
            with patch("core.chroma_client._get_client") as client:
                client.return_value.heartbeat.return_value = 1
                response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unreachable")


class RecoverStuckTasksTests(TestCase):
    def test_recent_pending_items_are_not_touched(self):
        Document.objects.create(
            title="جدید", file="documents/x.txt", status=Document.Status.PENDING
        )
        Question.objects.create(question="جدید", status=Question.Status.GENERATING)
        call_command("recover_stuck_tasks", stdout=StringIO())
        self.assertEqual(Document.objects.filter(status=Document.Status.PENDING).count(), 1)
        self.assertEqual(
            Question.objects.filter(status=Question.Status.GENERATING).count(), 1
        )

    def test_stuck_items_are_marked_failed(self):
        old = timezone.now() - timedelta(hours=2)
        document = Document.objects.create(
            title="گیر کرده", file="documents/x.txt", status=Document.Status.PENDING
        )
        Document.objects.filter(pk=document.pk).update(updated_at=old)
        question = Question.objects.create(
            question="گیر کرده", status=Question.Status.GENERATING
        )
        Question.objects.filter(pk=question.pk).update(created_at=old)

        call_command("recover_stuck_tasks", stdout=StringIO())

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertIn("ایندکس‌سازی", document.error_message)
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertIn("پاسخ‌دهی", question.error_message)

    def test_failed_and_done_items_are_not_touched(self):
        old = timezone.now() - timedelta(hours=2)
        document = Document.objects.create(
            title="ناموفق", file="documents/x.txt", status=Document.Status.FAILED
        )
        Document.objects.filter(pk=document.pk).update(updated_at=old)
        question = Question.objects.create(
            question="پاسخ داده", status=Question.Status.DONE
        )
        Question.objects.filter(pk=question.pk).update(created_at=old)

        call_command("recover_stuck_tasks", stdout=StringIO())

        document.refresh_from_db()
        question.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertEqual(question.status, Question.Status.DONE)
