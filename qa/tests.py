from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from qa.models import Question
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
        Question.objects.create(question="q", answer="existing")
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
        Question.objects.create(question="اولی")
        Question.objects.create(question="دومی")
        response = self.client.get("/api/questions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_status_filter(self):
        Question.objects.create(question="پاسخ داده شده", status=Question.Status.DONE)
        Question.objects.create(question="در انتظار")
        response = self.client.get("/api/questions/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["question"], "در انتظار")

    def test_delete_question_via_api(self):
        question = Question.objects.create(question="برای حذف")
        response = self.client.delete(f"/api/questions/{question.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())


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


class AnsweringServiceTests(APITestCase):
    def setUp(self):
        super().setUp()
        # A ready document lets the answering flow reach the retrieval/LLM steps;
        # the empty-corpus behavior is covered separately in NoCorpusAnswerTests.
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
                {"document_id": 1, "title": "گزارش فروش", "excerpt": "متن گزارش فروش کامل"},
                {"document_id": 2, "title": "گزارش دوم", "excerpt": "متن گزارش دوم"},
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

    def test_answer_llm_failure_sets_failed_status(self):
        question = Question.objects.create(question="سوال")

        class ExplodingLLM:
            def invoke(self, messages):
                raise RuntimeError("connection refused")

        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([]),
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
        vectorstore = self.FakeVectorStore([])

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

    def test_answered_at_is_set_only_on_success(self):
        question = Question.objects.create(question="سوال")
        llm = self.FakeLLM()
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([]),
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
                return_value=self.FakeVectorStore([]),
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
                return_value=self.FakeVectorStore([]),
            ),
            patch("qa.services.answering.get_llm", side_effect=PlainError("boom")),
        ):
            answer_question(question.pk)

        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.FAILED)
        self.assertEqual(question.error_message, "boom")

    def test_deleted_question_mid_task_does_not_crash(self):
        question = Question.objects.create(question="سوال")

        def delete_then_return(messages):
            Question.objects.filter(pk=question.pk).delete()
            return SimpleNamespace(content="پاسخ")

        llm = self.FakeLLM()
        llm.invoke = delete_then_return
        with (
            patch(
                "qa.services.answering.get_chroma_vectorstore",
                return_value=self.FakeVectorStore([]),
            ),
            patch("qa.services.answering.get_llm", return_value=llm),
        ):
            # Must not raise even though the row vanished mid-task
            answer_question(question.pk)
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())


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
        Document.objects.create(
            title="ناموفق", file="documents/failed.txt", status=Document.Status.FAILED
        )
        question = Question.objects.create(question="سوال")
        with patch("qa.services.answering.get_llm") as llm:
            answer_question(question.pk)

        llm.assert_not_called()
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.DONE)
