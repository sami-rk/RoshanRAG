import csv
import json

from django.http import HttpResponse, JsonResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

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