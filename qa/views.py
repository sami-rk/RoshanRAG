from rest_framework import mixins, viewsets

from .models import Question
from .serializers import QuestionSerializer
from .services.answering import schedule_answering


class QuestionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer

    def perform_create(self, serializer):
        question = serializer.save()
        schedule_answering(question.pk)