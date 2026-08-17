from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from qa.models import Question

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
        from unittest.mock import patch

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
        question = Question.objects.create(question="q", answer="existing")
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