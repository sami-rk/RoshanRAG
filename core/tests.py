import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from documents.models import Document
from qa.models import Question


class SqlitePragmaTests(TestCase):
    def test_connection_created_applies_busy_timeout(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout")
            self.assertEqual(cursor.fetchone()[0], 5000)


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
        with patch("documents.signals.schedule_index"):
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
        with patch("documents.signals.schedule_index"):
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
        with patch("documents.signals.schedule_index"):
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


class PublicPagesTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "روشن")

    def test_about_page_renders(self):
        response = self.client.get("/about/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "درباره روشن RAG")

    def test_pricing_page_renders(self):
        response = self.client.get("/pricing/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تعرفه‌ها")

    def test_contact_page_renders(self):
        response = self.client.get("/contact/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تماس با ما")


class LanguageToggleTests(TestCase):
    def test_switching_to_english_sticks_in_session(self):
        response = self.client.get("/set-language/?lang=en&next=/pricing/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/pricing/")
        response = self.client.get("/pricing/")
        self.assertContains(response, "pricing")

    def test_invalid_language_falls_back_to_default(self):
        response = self.client.get("/set-language/?lang=xx&next=/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_offsite_next_is_dropped(self):
        response = self.client.get(
            "/set-language/?lang=en&next=https://evil.example/phish"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")


class DefaultLanguageTests(TestCase):
    def test_defaults_to_persian_for_a_fresh_visitor(self):
        response = self.client.get("/")
        self.assertContains(response, "سامانه هوشمند پرسش از اسناد سازمانی")
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')

    def test_defaults_to_persian_even_with_an_english_accept_language(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertContains(response, 'lang="fa"')
        self.assertContains(response, 'dir="rtl"')


class ErrorPageTests(TestCase):
    def test_server_error_renders_styled_page(self):
        from django.test import RequestFactory

        from core.views import server_error

        request = RequestFactory().get("/")
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "خطایی در سرور رخ داد", status_code=500)

    @override_settings(DEBUG=False)
    def test_not_found_renders_styled_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "صفحه موردنظر یافت نشد", status_code=404)

    def test_favicon_redirects_to_the_svg(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"], "/static/admin/img/roshan-favicon.svg"
        )


class MediaAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester", password="pass"
        )

    def test_chat_page_is_public_for_anonymous_visitors(self):
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "وارد شوید")

    def test_chat_page_shows_form_for_authenticated_users(self):
        self.client.force_login(self.user)
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ask-form")
        self.assertContains(response, "csrfmiddlewaretoken")

    @staticmethod
    def _media_root():
        directory = tempfile.mkdtemp()
        Path(directory, "secret.txt").write_text("متن محرمانه", encoding="utf-8")
        return directory

    def test_anonymous_request_is_denied(self):
        with override_settings(MEDIA_ROOT=self._media_root()):
            response = self.client.get("/media/secret.txt")
        self.assertEqual(response.status_code, 403)

    def test_session_authenticated_user_can_download(self):
        with override_settings(MEDIA_ROOT=self._media_root()):
            self.client.force_login(self.user)
            response = self.client.get("/media/secret.txt")
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(body, "متن محرمانه")

    def test_token_authenticated_user_can_download(self):
        token = Token.objects.create(user=self.user)
        with override_settings(MEDIA_ROOT=self._media_root()):
            response = self.client.get(
                "/media/secret.txt", HTTP_AUTHORIZATION=f"Token {token.key}"
            )
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(body, "متن محرمانه")

    def test_invalid_token_is_denied(self):
        with override_settings(MEDIA_ROOT=self._media_root()):
            response = self.client.get(
                "/media/secret.txt", HTTP_AUTHORIZATION="Token not-a-real-key"
            )
        self.assertEqual(response.status_code, 403)


class AnalyticsTests(TestCase):
    def test_questions_per_day_reports_all_days(self):
        from core.stats import get_questions_per_day

        Question.objects.create(question="امروز", status=Question.Status.DONE)
        series = get_questions_per_day(days=30)
        self.assertEqual(len(series), 30)
        self.assertEqual(series[-1]["count"], 1)
        self.assertEqual(series[0]["count"], 0)

    def test_feedback_counts_grouped(self):
        from core.stats import get_feedback_counts

        Question.objects.create(question="یک", feedback=Question.Feedback.UP)
        Question.objects.create(question="دو", feedback=Question.Feedback.UP)
        Question.objects.create(question="سه", feedback=Question.Feedback.DOWN)
        counts = get_feedback_counts()
        self.assertEqual(counts["up"], 2)
        self.assertEqual(counts["down"], 1)

    def test_top_documents_by_usage(self):
        from core.stats import get_top_documents

        document = Document.objects.create(
            title="سند پرکاربرد", file="documents/x.txt", status=Document.Status.READY
        )
        Question.objects.create(
            question="پرسش",
            sources=[{"document_id": document.pk, "title": document.title}],
        )
        top = get_top_documents()
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["title"], "سند پرکاربرد")
        self.assertEqual(top[0]["uses"], 1)

    def test_analytics_page_renders_for_staff(self):
        user = get_user_model().objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.client.force_login(user)
        response = self.client.get("/admin/analytics/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "analytics-data")
        self.assertContains(response, "chart-questions")

    def test_analytics_page_requires_staff(self):
        response = self.client.get("/admin/analytics/")
        self.assertEqual(response.status_code, 302)
