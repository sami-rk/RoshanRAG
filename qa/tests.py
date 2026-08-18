from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from qa.models import Question, Thread
from qa.services.answering import _dedupe_by_document, answer_question, friendly_llm_error

User = get_user_model()


class QuestionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client.force_authenticate(user=self.user)

    def test_list_requires_authentication(self):
        anonymous = self.client_class()
        response = anonymous.get("/api/questions/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_question_schedules_answering(self):
        with patch("qa.views.schedule_answering") as schedule:
            response = self.client.post(
                "/api/questions/", {"question": "چه سندی دارید؟"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        schedule.assert_called_once_with(response.data["id"])
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.status, Question.Status.PENDING)

    def test_create_question_rejects_blank(self):
        response = self.client.post("/api/questions/", {"question": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_write_fields_are_read_only(self):
        Question.objects.create(question="q", answer="existing", user=self.user)
        with patch("qa.views.schedule_answering"):
            response = self.client.post(
                "/api/questions/",
                {"question": "q", "answer": "forged", "status": Question.Status.DONE},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Question.objects.get(pk=response.data["id"])
        self.assertEqual(created.answer, "")
        self.assertEqual(created.status, Question.Status.PENDING)

    def test_history_is_listed(self):
        Question.objects.create(question="اولی", user=self.user)
        Question.objects.create(question="دومی", user=self.user)
        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_status_filter(self):
        Question.objects.create(
            question="پاسخ داده شده", status=Question.Status.DONE, user=self.user
        )
        Question.objects.create(question="در انتظار", user=self.user)
        response = self.client.get("/api/questions/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["question"], "در انتظار")

    def test_delete_question_via_api(self):
        question = Question.objects.create(question="برای حذف", user=self.user)
        response = self.client.delete(f"/api/questions/{question.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())

    def test_feedback_defaults_to_none(self):
        question = Question.objects.create(question="پرسش", user=self.user)
        self.assertEqual(question.feedback, Question.Feedback.NONE)

    def test_feedback_can_be_updated(self):
        question = Question.objects.create(
            question="پرسش", status=Question.Status.DONE, user=self.user
        )
        response = self.client.patch(
            f"/api/questions/{question.pk}/", {"feedback": "up"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feedback"], "up")
        question.refresh_from_db()
        self.assertEqual(question.feedback, Question.Feedback.UP)

    def test_feedback_rejects_invalid_values(self):
        question = Question.objects.create(question="پرسش", user=self.user)
        response = self.client.patch(
            f"/api/questions/{question.pk}/", {"feedback": "maybe"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        question.refresh_from_db()
        self.assertEqual(question.feedback, Question.Feedback.NONE)

    def test_export_csv_returns_selected_questions(self):
        Question.objects.create(
            question="سوال اول",
            answer="پاسخ اول",
            status=Question.Status.DONE,
            user=self.user,
        )
        response = self.client.get("/api/questions/export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Content-Disposition", response)
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("\ufeff"))
        self.assertIn("id,question,answer,status,feedback", content)
        self.assertIn("سوال اول", content)
        self.assertIn("پاسخ اول", content)

    def test_export_json_returns_selected_questions(self):
        Question.objects.create(question="سوال دوم", user=self.user)
        response = self.client.get("/api/questions/export/?format=json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["results"][0]["question"], "سوال دوم")

    def test_export_respects_status_filter(self):
        Question.objects.create(
            question="انجام شده", status=Question.Status.DONE, user=self.user
        )
        Question.objects.create(question="در انتظار", user=self.user)
        response = self.client.get("/api/questions/export/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode("utf-8")
        self.assertIn("در انتظار", content)
        self.assertNotIn("انجام شده", content)

    def test_demo_ask_creates_question_without_login(self):
        with patch("qa.views.schedule_answering") as schedule:
            response = self.client.post(
                "/api/questions/demo_ask/", {"question": "سوال دمو"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["demo_token"])
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.question, "سوال دمو")
        self.assertIsNotNone(question.demo_token)
        schedule.assert_called_once_with(question.pk)

    def test_demo_ask_rejects_empty_question(self):
        response = self.client.post(
            "/api/questions/demo_ask/", {"question": "   "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_demo_retrieve_requires_matching_token(self):
        with patch("qa.views.schedule_answering"):
            question = Question.objects.create(
                question="پرسش", demo_token=uuid4()
            )
        response = self.client.get(f"/api/questions/{question.pk}/demo/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(
            f"/api/questions/{question.pk}/demo/?token=wrong"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(
            f"/api/questions/{question.pk}/demo/?token={question.demo_token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["question"], "پرسش")

    def test_demo_retrieve_hides_normal_questions(self):
        with patch("qa.views.schedule_answering"):
            question = Question.objects.create(question="عادی")
        response = self.client.get(
            f"/api/questions/{question.pk}/demo/?token=abc"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_demo_endpoints_are_rate_limited_separately(self):
        from django.core.cache import cache
        from rest_framework.throttling import SimpleRateThrottle

        cache.clear()
        self.addCleanup(cache.clear)
        rates = {
            "user": "300/minute",
            "anon": "30/minute",
            "demo": "1/minute",
        }
        with (
            patch("qa.views.schedule_answering"),
            patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates),
        ):
            first = self.client.post(
                "/api/questions/demo_ask/", {"question": "اول"}, format="json"
            )
            self.assertEqual(first.status_code, status.HTTP_201_CREATED)
            second = self.client.post(
                "/api/questions/demo_ask/", {"question": "دوم"}, format="json"
            )
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_demo_retrieve_has_its_own_poll_throttle(self):
        from django.core.cache import cache
        from rest_framework.throttling import SimpleRateThrottle

        cache.clear()
        self.addCleanup(cache.clear)
        rates = {
            "user": "300/minute",
            "anon": "30/minute",
            "demo": "1/minute",
            "demo_poll": "1/second",
        }
        with (
            patch("qa.views.schedule_answering"),
            patch.object(SimpleRateThrottle, "THROTTLE_RATES", rates),
        ):
            question = Question.objects.create(
                question="پرسش", demo_token=uuid4()
            )
            url = f"/api/questions/{question.pk}/demo/?token={question.demo_token}"
            anonymous = self.client_class()
            # demo_ask budget is already exhausted by other requests in this
            # window, but the poll endpoint must not share that scope.
            self.client.post("/api/questions/demo_ask/", {"question": "اول"}, format="json")
            response = anonymous.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["question"], "پرسش")
            # And it honors its own rate: a second poll within the same second
            # is throttled.
            second = anonymous.get(url)
            self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_create_question_without_thread_creates_one(self):
        with patch("qa.views.schedule_answering"):
            response = self.client.post(
                "/api/questions/", {"question": "پرسش بدون گفتگو"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(pk=response.data["id"])
        self.assertIsNotNone(question.thread)
        self.assertEqual(question.thread.title, "پرسش بدون گفتگو")

    def test_create_question_in_existing_thread(self):
        thread = Thread.objects.create(title="گفتگوی من", user=self.user)
        with patch("qa.views.schedule_answering"):
            response = self.client.post(
                "/api/questions/",
                {"question": "سوال در گفتگو", "thread": str(thread.pk)},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.thread, thread)
        self.assertEqual(question.user, self.user)

    def test_question_list_filters_by_thread(self):
        thread = Thread.objects.create(title="گفتگو", user=self.user)
        Question.objects.create(question="در گفتگو", thread=thread, user=self.user)
        Question.objects.create(question="بیرون گفتگو", user=self.user)
        response = self.client.get(f"/api/questions/?thread={thread.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_question_patch_cannot_rewrite_question_text(self):
        question = Question.objects.create(question="اصلی", user=self.user)
        response = self.client.patch(
            f"/api/questions/{question.pk}/",
            {"question": "تغییر یافته", "feedback": "down"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        question.refresh_from_db()
        self.assertEqual(question.question, "اصلی")
        self.assertEqual(question.feedback, Question.Feedback.DOWN)

    def test_create_question_assigns_owner(self):
        with patch("qa.views.schedule_answering"):
            response = self.client.post(
                "/api/questions/", {"question": "پرسش مالکانه"}, format="json"
            )
        question = Question.objects.get(pk=response.data["id"])
        self.assertEqual(question.user, self.user)
        self.assertEqual(question.thread.user, self.user)

    def test_cannot_create_question_in_someone_elses_thread(self):
        other = User.objects.create_user(username="other", password="pass")
        thread = Thread.objects.create(title="گفتگوی دیگران", user=other)
        response = self.client.post(
            "/api/questions/",
            {"question": "نفوذ", "thread": str(thread.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_retrieve_someone_elses_question(self):
        other = User.objects.create_user(username="other", password="pass")
        question = Question.objects.create(question="محرمانه", user=other)
        response = self.client.get(f"/api/questions/{question.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_patch_someone_elses_question(self):
        other = User.objects.create_user(username="other", password="pass")
        question = Question.objects.create(question="محرمانه", user=other)
        response = self.client.patch(
            f"/api/questions/{question.pk}/", {"feedback": "up"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_someone_elses_question(self):
        other = User.objects.create_user(username="other", password="pass")
        question = Question.objects.create(question="محرمانه", user=other)
        response = self.client.delete(f"/api/questions/{question.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())

    def test_cannot_stream_someone_elses_question(self):
        other = User.objects.create_user(username="other", password="pass")
        question = Question.objects.create(
            question="محرمانه",
            answer="پاسخ",
            status=Question.Status.DONE,
            user=other,
        )
        response = self.client.get(f"/api/questions/{question.pk}/stream/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_hides_other_users_and_demo_questions(self):
        other = User.objects.create_user(username="other", password="pass")
        Question.objects.create(question="مال من", user=self.user)
        Question.objects.create(question="مال دیگران", user=other)
        Question.objects.create(question="دمو")
        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["question"], "مال من")

    def test_export_is_scoped_to_owner(self):
        other = User.objects.create_user(username="other", password="pass")
        Question.objects.create(question="مال من", user=self.user)
        Question.objects.create(question="مال دیگران", user=other)
        response = self.client.get("/api/questions/export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("مال من", response.content.decode("utf-8"))
        self.assertNotIn("مال دیگران", response.content.decode("utf-8"))


class ThreadAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client.force_authenticate(user=self.user)

    def test_threads_are_listed(self):
        Thread.objects.create(title="گفتگوی اول", user=self.user)
        Thread.objects.create(title="گفتگوی دوم", user=self.user)
        response = self.client.get("/api/threads/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_thread_retrieve_includes_questions(self):
        thread = Thread.objects.create(title="گفتگو", user=self.user)
        Question.objects.create(question="سوال یک", thread=thread, user=self.user)
        response = self.client.get(f"/api/threads/{thread.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "گفتگو")
        self.assertEqual(len(response.data["questions"]), 1)
        self.assertEqual(response.data["question_count"], 1)

    def test_thread_can_be_created(self):
        response = self.client.post(
            "/api/threads/", {"title": "گفتگوی جدید"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["id"])
        thread = Thread.objects.get(pk=response.data["id"])
        self.assertEqual(thread.user, self.user)

    def test_cannot_list_someone_elses_thread(self):
        other = User.objects.create_user(username="other", password="pass")
        Thread.objects.create(title="گفتگوی دیگران", user=other)
        response = self.client.get("/api/threads/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_cannot_retrieve_someone_elses_thread(self):
        other = User.objects.create_user(username="other", password="pass")
        thread = Thread.objects.create(title="گفتگوی دیگران", user=other)
        response = self.client.get(f"/api/threads/{thread.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stream_endpoint_emits_done_event_for_finished_question(self):
        question = Question.objects.create(
            question="سوال",
            answer="پاسخ کامل",
            status=Question.Status.DONE,
            stream_data="",
            user=self.user,
        )
        response = self.client.get(f"/api/questions/{question.pk}/stream/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("text/event-stream", response["Content-Type"])
        self.assertIn("پاسخ کامل", body)
        self.assertIn('"type": "done"', body)

    def test_stream_done_frame_serializes_question_in_thread(self):
        thread = Thread.objects.create(title="گفتگو", user=self.user)
        question = Question.objects.create(
            question="سوال در گفتگو",
            answer="پاسخ",
            status=Question.Status.DONE,
            stream_data="",
            thread=thread,
            user=self.user,
        )
        response = self.client.get(f"/api/questions/{question.pk}/stream/")
        body = b"".join(response.streaming_content).decode("utf-8")
        done = [line for line in body.split("\n") if '"type": "done"' in line]
        self.assertTrue(done)
        self.assertIn(str(thread.pk), done[0])

    def test_stream_endpoint_emits_buffered_tokens_then_done(self):
        question = Question.objects.create(
            question="سوال",
            answer="پاسخ کامل",
            status=Question.Status.DONE,
            stream_data="بخش اول ",
            user=self.user,
        )
        response = self.client.get(f"/api/questions/{question.pk}/stream/")
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("بخش اول", body)
        self.assertIn("پاسخ کامل", body)

    def test_stream_requires_authentication(self):
        question = Question.objects.create(question="سوال")
        anonymous = self.client_class()
        response = anonymous.get(f"/api/questions/{question.pk}/stream/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stream_emits_keepalive_while_idle(self):
        import itertools

        from qa.views import _sse_events

        question = Question.objects.create(
            question="سوال", status=Question.Status.PENDING, user=self.user
        )
        frames = list(
            itertools.islice(
                _sse_events(question.pk, poll_interval=0.01, keepalive_interval=0),
                3,
            )
        )
        self.assertEqual(frames, [": keepalive\n\n"] * 3)


class FriendlyErrorTests(APITestCase):
    def test_json_string_body_is_unwrapped(self):
        class Exc(Exception):
            def __init__(self):
                super().__init__("Response validation failed: ...")
                self.body = '{ "success": false, "error": "Access denied by security policy." }'

        self.assertEqual(friendly_llm_error(Exc()), "Access denied by security policy.")

    def test_dict_body_with_error_object(self):
        class Exc(Exception):
            def __init__(self):
                super().__init__("x")
                self.body = {"error": {"message": "Rate limit exceeded"}}

        self.assertEqual(friendly_llm_error(Exc()), "Rate limit exceeded")

    def test_pydantic_validation_error(self):
        class Exc(Exception):
            def errors(self):
                return [{"input_value": "The real cause"}]

        self.assertEqual(friendly_llm_error(Exc()), "The real cause")

    def test_plain_message_passthrough(self):
        class Exc(Exception):
            pass

        self.assertEqual(friendly_llm_error(Exc("connection refused")), "connection refused")


class AdminOwnerDisplayTests(TestCase):
    def test_question_admin_shows_the_owner(self):
        from qa.admin import QuestionAdmin

        self.assertIn("user", QuestionAdmin.list_display)
        self.assertIn("user", QuestionAdmin.list_filter)

    def test_thread_admin_is_registered_with_its_owner(self):
        from qa.admin import ThreadAdmin
        from qa.admin import roshan_admin_site

        model_admin = roshan_admin_site._registry[Thread]
        self.assertIsInstance(model_admin, ThreadAdmin)
        self.assertIn("user", model_admin.list_display)
        self.assertIn("user", model_admin.list_filter)

    def test_question_admin_is_registered_with_the_owner(self):
        from qa.admin import QuestionAdmin
        from qa.admin import roshan_admin_site

        model_admin = roshan_admin_site._registry[Question]
        self.assertIsInstance(model_admin, QuestionAdmin)


class AnsweringServiceTests(APITestCase):
    def setUp(self):
        super().setUp()
        # A ready document lets the answering flow reach the retrieval/LLM steps;
        # the empty-corpus behavior is covered separately in NoCorpusAnswerTests.
        # The post_save signal is patched so no real indexing thread (which would
        # touch Chroma and the test database) is spawned during tests.
        with patch("documents.signals.schedule_index"):
            self.document = Document.objects.create(
                title="سند آماده",
                file="documents/ready.txt",
                status=Document.Status.READY,
            )

    @staticmethod
    def _fake_doc(document_id, title, content):
        return SimpleNamespace(
            metadata={"document_id": document_id, "title": title},
            page_content=content,
        )

    class FakeVectorStore:
        def __init__(self, retrieved):
            self.retrieved = retrieved
            self.last_query = None
            self.last_k = None
            self.last_fetch_k = None

        def max_marginal_relevance_search(self, query, k, fetch_k):
            self.last_query = query
            self.last_k = k
            self.last_fetch_k = fetch_k
            return self.retrieved

    class FakeLLM:
        def __init__(self, content="پاسخ تولیدشده"):
            self.content = content
            self.messages = None

        def stream(self, messages):
            self.messages = messages
            if isinstance(self.content, list):
                for item in self.content:
                    yield SimpleNamespace(content=item)
            else:
                yield SimpleNamespace(content=self.content)

        def invoke(self, messages):
            self.messages = messages
            return SimpleNamespace(content=self.content)

    def test_answer_success_saves_answer_and_sources(self):
        question = Question.objects.create(question="میزان فروش چقدر است؟")
        retrieved = [
            self._fake_doc(1, "گزارش فروش", "متن گزارش فروش کامل"),
            self._fake_doc(2, "گزارش دوم", "متن گزارش دوم"),
        ]
        vectorstore = self.FakeVectorStore(retrieved)
        llm = self.FakeLLM("پاسخ: ۱۲.۵ میلیارد")

        with (
            patch("qa.services.answering.get_chroma_vectorstore", return_value=vectorstore),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertEqual(question.answer, "پاسخ: ۱۲.۵ میلیارد")
        self.assertEqual(
            question.sources,
            [
                {
                    "document_id": 1,
                    "title": "گزارش فروش",
                    "excerpt": "متن گزارش فروش کامل",
                    "citation": 1,
                },
                {
                    "document_id": 2,
                    "title": "گزارش دوم",
                    "excerpt": "متن گزارش دوم",
                    "citation": 2,
                },
            ],
        )
        self.assertIsNotNone(question.answered_at)
        self.assertEqual(question.error_message, "")
        # The vector store was queried with MMR using the question text and top-k settings
        self.assertEqual(vectorstore.last_query, "میزان فروش چقدر است؟")
        self.assertEqual(vectorstore.last_k, 4)
        self.assertEqual(vectorstore.last_fetch_k, 20)
        # The LLM received a system prompt and a human prompt with the context
        self.assertIsNotNone(llm.messages)
        self.assertIn("اسناد", llm.messages[-1].content)
        self.assertIn("متن گزارش فروش کامل", llm.messages[-1].content)

    def test_answer_dedupes_chunks_from_same_document(self):
        question = Question.objects.create(question="سوال")
        retrieved = [
            self._fake_doc(1, "سند الف", "چانک اول"),
            self._fake_doc(1, "سند الف", "چانک دوم"),
            self._fake_doc(2, "سند ب", "چانک سوم"),
            self._fake_doc(3, "سند ج", "چانک چهارم"),
        ]
        vectorstore = self.FakeVectorStore(retrieved)
        llm = self.FakeLLM()

        with (
            patch("qa.services.answering.get_chroma_vectorstore", return_value=vectorstore),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        document_ids = [source["document_id"] for source in question.sources]
        self.assertEqual(document_ids, [1, 2, 3])  # one chunk per document, max 3 docs
        self.assertEqual(len(question.sources), 3)

    def test_answer_skips_llm_when_retrieval_is_empty(self):
        question = Question.objects.create(question="سوال بدون سند مرتبط")
        vectorstore = self.FakeVectorStore([])
        llm = self.FakeLLM()

        with (
            patch("qa.services.answering.get_chroma_vectorstore", return_value=vectorstore),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertIn("مرتبط", question.answer)
        self.assertEqual(question.sources, [])
        self.assertIsNotNone(question.answered_at)
        self.assertEqual(question.error_message, "")
        self.assertIsNone(llm.messages)  # the LLM was never invoked

    def test_answer_llm_failure_sets_failed_status(self):
        question = Question.objects.create(question="سوال")

        class ExplodingLLM:
            def invoke(self, messages):
                raise RuntimeError("connection refused")

        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=ExplodingLLM()),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertIn("connection refused", question.error_message)
        self.assertEqual(question.answer, "")
        self.assertEqual(question.sources, [])
        self.assertIsNone(question.answered_at)

    def test_answer_transitions_through_generating(self):
        question = Question.objects.create(question="سوال")

        def assert_generating(*args, **kwargs):
            question.refresh_from_db()
            self.assertEqual(question.status, Question.Status.GENERATING)

        llm = self.FakeLLM()
        vectorstore = self.FakeVectorStore([self._fake_doc(1, "سند", "متن")])

        # Simulate the status being saved mid-flight by wrapping the LLM call
        original_invoke = llm.invoke

        def invoke_with_check(messages):
            assert_generating()
            return original_invoke(messages)

        llm.invoke = invoke_with_check

        with (
            patch("qa.services.answering.get_chroma_vectorstore", return_value=vectorstore),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)

    def test_dedupe_by_document_limits_to_max_docs(self):
        docs = [self._fake_doc(i, f"سند {i}", "متن") for i in range(1, 7)]
        result = _dedupe_by_document(docs, max_docs=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(
            [d.metadata["document_id"] for d in result], [1, 2]
        )

    def test_dedupe_by_document_skips_duplicates(self):
        docs = [
            self._fake_doc(1, "سند الف", "اول"),
            self._fake_doc(1, "سند الف", "دوم"),
            self._fake_doc(2, "سند ب", "سوم"),
        ]
        result = _dedupe_by_document(docs, max_docs=10)
        self.assertEqual(len(result), 2)
        self.assertEqual([d.metadata["document_id"] for d in result], [1, 2])

    def test_answer_content_none_is_stored_as_empty_string(self):
        question = Question.objects.create(question="سوال")
        llm = self.FakeLLM(content=None)
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertEqual(question.answer, "")
        self.assertEqual(len(question.sources), 1)
        self.assertEqual(question.sources[0]["document_id"], 1)

    def test_answer_content_list_is_coerced_to_text(self):
        question = Question.objects.create(question="سوال")
        llm = self.FakeLLM(content=["بخش اول", {"text": "بخش دوم"}])
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertIsInstance(question.answer, str)
        self.assertIn("بخش اول", question.answer)

    def test_answered_at_is_set_only_on_success(self):
        question = Question.objects.create(question="سوال")
        llm = self.FakeLLM()
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)
        question.refresh_from_db()
        self.assertIsNotNone(question.answered_at)
        self.assertLessEqual(question.answered_at, timezone.now())

    def test_llm_error_is_stored_readably(self):
        question = Question.objects.create(question="سوال")

        class ProviderError(Exception):
            def __init__(self):
                super().__init__("Response validation failed: ...")
                self.body = '{ "success": false, "error": "Access denied by security policy." }'

        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", side_effect=ProviderError()),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertEqual(question.error_message, "Access denied by security policy.")

    def test_plain_exception_keeps_its_message(self):
        question = Question.objects.create(question="سوال")

        class PlainError(Exception):
            pass

        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", side_effect=PlainError("boom")),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertEqual(question.error_message, "boom")

    def test_deleted_question_mid_task_does_not_crash(self):
        question = Question.objects.create(question="سوال")

        def delete_then_stream(messages):
            Question.objects.filter(pk=question.pk).delete()
            yield SimpleNamespace(content="پاسخ")
            yield SimpleNamespace(content=" تکمیل")

        llm = self.FakeLLM()
        llm.stream = delete_then_stream
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            # Must not raise even though the row vanished mid-task
            answer_question(question.pk)
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())

    def test_answer_streams_tokens_into_stream_data(self):
        question = Question.objects.create(question="سوال")

        class ChunkingLLM:
            def stream(self, messages):
                for word in ["قسمت ", "اول، ", "قسمت ", "دوم. ", "پایان."]:
                    yield SimpleNamespace(content=word)

        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=ChunkingLLM()),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertEqual(question.answer, "قسمت اول، قسمت دوم. پایان.")
        self.assertEqual(question.stream_data, "قسمت اول، قسمت دوم. پایان.")

    def test_answer_falls_back_to_invoke_when_stream_fails(self):
        question = Question.objects.create(question="سوال")

        class BrokenStreamLLM(self.FakeLLM):
            def stream(self, messages):
                raise RuntimeError("streaming not supported")
                yield

        llm = BrokenStreamLLM("پاسخ از invoke")
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([self._fake_doc(1, "سند", "متن")]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertEqual(question.answer, "پاسخ از invoke")
        self.assertEqual(question.stream_data, "پاسخ از invoke")

    def test_answer_skips_question_already_generating(self):
        question = Question.objects.create(
            question="سوال", status=Question.Status.GENERATING
        )
        with (
            patch("qa.services.answering.get_chroma_vectorstore") as vectorstore,
            patch("qa.services.answering.get_llm") as llm,
        ):
            answer_question(question.pk)

        vectorstore.assert_not_called()
        llm.assert_not_called()
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.GENERATING)
        self.assertEqual(question.answer, "")


class QuestionAdminActionTests(TestCase):
    def _admin_request(self):
        request = RequestFactory().get("/")
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_retry_answering_skips_generating_questions(self):
        from core.admin_site import roshan_admin_site
        from qa.admin import QuestionAdmin

        generating = Question.objects.create(
            question="در حال تولید", status=Question.Status.GENERATING
        )
        failed = Question.objects.create(
            question="ناموفق", status=Question.Status.FAILED
        )
        request = self._admin_request()
        with patch("qa.admin.schedule_answering") as schedule:
            QuestionAdmin(Question, roshan_admin_site).retry_answering(
                request, Question.objects.filter(pk__in=[generating.pk, failed.pk])
            )
        schedule.assert_called_once_with(failed.pk)
        levels = [msg.level for msg in request._messages]
        self.assertIn(messages.WARNING, levels)


class NoCorpusAnswerTests(TestCase):
    def test_answers_without_llm_when_no_ready_documents(self):
        question = Question.objects.create(question="سوال")
        with (
            patch("qa.services.answering.get_chroma_vectorstore") as vectorstore,
            patch("qa.services.answering.get_llm") as llm,
        ):
            answer_question(question.pk)

        vectorstore.assert_not_called()
        llm.assert_not_called()
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
        self.assertIn("سند", question.answer)
        self.assertEqual(question.error_message, "")
        self.assertEqual(question.sources, [])
        self.assertIsNotNone(question.answered_at)

    def test_pending_document_does_not_count_as_a_corpus(self):
        with patch("documents.signals.schedule_index"):
            Document.objects.create(
                title="در انتظار",
                file="documents/pending.txt",
                status=Document.Status.PENDING,
            )
        question = Question.objects.create(question="سوال")
        with (
            patch("qa.services.answering.get_chroma_vectorstore") as vectorstore,
            patch("qa.services.answering.get_llm") as llm,
        ):
            answer_question(question.pk)

        vectorstore.assert_not_called()
        llm.assert_not_called()
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)

    def test_failed_only_corpus_answers_without_llm(self):
        with patch("documents.signals.schedule_index"):
            Document.objects.create(
                title="ناموفق", file="documents/failed.txt", status=Document.Status.FAILED
            )
        question = Question.objects.create(question="سوال")
        with patch("qa.services.answering.get_llm") as llm:
            answer_question(question.pk)

        llm.assert_not_called()
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)


class ScheduleAnsweringTests(TestCase):
    def test_marks_question_failed_when_worker_dies(self):
        from qa.services.answering import schedule_answering

        question = Question.objects.create(question="پرسش")
        with patch("qa.services.answering.run_in_background") as run:
            schedule_answering(question.pk)
        on_error = run.call_args.kwargs["on_error"]
        on_error(RuntimeError("boom"))
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertEqual(question.error_message, "boom")

    def test_ignores_deleted_question(self):
        from qa.services.answering import schedule_answering

        question = Question.objects.create(question="پرسش")
        with patch("qa.services.answering.run_in_background") as run:
            schedule_answering(question.pk)
        question.delete()
        run.call_args.kwargs["on_error"](RuntimeError("boom"))
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())
