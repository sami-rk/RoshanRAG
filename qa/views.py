import csv
import json
import uuid

from django.http import HttpResponse, JsonResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Question
from .serializers import QuestionSerializer
from .services.answering import schedule_answering

EXPORT_COLUMNS = [
    "id",
    "question",
    "answer",
    "status",
    "feedback",
    "sources",
    "error_message",
    "created_at",
    "answered_at",
]


class QuestionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def perform_create(self, serializer):
        question = serializer.save()
        schedule_answering(question.pk)

    @action(detail=False, methods=["get"])
    def export(self, request):
        rows = list(
            self.filter_queryset(self.get_queryset()).values(*EXPORT_COLUMNS)
        )
        if request.query_params.get("format", "csv").lower() == "json":
            return JsonResponse(
                {"results": rows}, json_dumps_params={"ensure_ascii": False}
            )
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="questions.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(EXPORT_COLUMNS)
        for row in rows:
            row = dict(row)
            if row["sources"] is None:
                row["sources"] = ""
            else:
                row["sources"] = json.dumps(row["sources"], ensure_ascii=False)
            writer.writerow([row[column] for column in EXPORT_COLUMNS])
        return response

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def demo_ask(self, request):
        question_text = (request.data.get("question") or "").strip()
        if not question_text:
            return Response(
                {"detail": "متن پرسش الزامی است."}, status=status.HTTP_400_BAD_REQUEST
            )
        question = Question.objects.create(
            question=question_text, demo_token=uuid.uuid4()
        )
        schedule_answering(question.pk)
        data = QuestionSerializer(question, context=self.get_serializer_context()).data
        data["demo_token"] = str(question.demo_token)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny], url_path="demo")
    def demo_retrieve(self, request, pk=None):
        question = self.get_object()
        token = request.query_params.get("token")
        if question.demo_token is None or token != str(question.demo_token):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            QuestionSerializer(question, context=self.get_serializer_context()).data
        )