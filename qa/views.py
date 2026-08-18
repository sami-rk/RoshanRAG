import csv
import json
import time
import uuid

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from .models import Question, Thread
from .serializers import QuestionSerializer, ThreadSerializer
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


def _sse_events(pk, poll_interval=0.3, keepalive_interval=15):
    """Yield Server-Sent Events for a question's answer stream.

    ``keepalive_interval`` controls how often an SSE comment line (ignored by
    EventSource clients) is emitted while the stream is idle, so reverse
    proxies that drop silent connections do not cut the stream off mid-answer.
    """
    sent = 0
    last_activity = time.time()
    deadline = time.time() + 300
    while True:
        try:
            question = Question.objects.get(pk=pk)
        except Question.DoesNotExist:
            yield f"data: {json.dumps({'type': 'error', 'detail': 'پرسش یافت نشد'}, ensure_ascii=False, default=str)}\n\n"
            return
        data = question.stream_data
        if len(data) > sent:
            yield (
                f"data: {json.dumps({'type': 'token', 'text': data[sent:]}, ensure_ascii=False, default=str)}\n\n"
            )
            sent = len(data)
            last_activity = time.time()
        elif time.time() - last_activity >= keepalive_interval:
            yield ": keepalive\n\n"
            last_activity = time.time()
        if question.status in (Question.Status.DONE, Question.Status.FAILED):
            payload = QuestionSerializer(question).data
            yield (
                f"data: {json.dumps({'type': 'done', 'question': payload}, ensure_ascii=False, default=str)}\n\n"
            )
            return
        if time.time() > deadline:
            yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
            return
        time.sleep(poll_interval)


class DemoPollRateThrottle(SimpleRateThrottle):
    scope = "demo_poll"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


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
    # Used by ScopedRateThrottle on the anonymous demo endpoints; the other
    # actions keep the global user/anon throttles.
    throttle_scope = "demo"

    def get_queryset(self):
        # Questions are private to the user who asked them. Demo questions
        # (created anonymously with ``user=None``) stay out of every list.
        queryset = super().get_queryset().filter(user=self.request.user)
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        thread = self.request.query_params.get("thread")
        if thread:
            queryset = queryset.filter(thread_id=thread)
        return queryset

    def perform_create(self, serializer):
        validated = serializer.validated_data
        thread = validated.get("thread")
        if thread is not None and thread.user_id != self.request.user.id:
            raise serializers.ValidationError(
                {"thread": "گفتگو متعلق به شما نیست."}
            )
        if thread is None:
            thread = Thread.objects.create(
                title=validated["question"][:60], user=self.request.user
            )
            validated["thread"] = thread
        question = serializer.save(user=self.request.user)
        schedule_answering(question.pk)

    @action(detail=True, methods=["get"])
    def stream(self, request, pk=None):
        self.get_object()
        response = StreamingHttpResponse(
            _sse_events(pk), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

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

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], throttle_classes=[ScopedRateThrottle])
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

    @action(detail=True, methods=["get"], permission_classes=[AllowAny], throttle_classes=[DemoPollRateThrottle], url_path="demo")
    def demo_retrieve(self, request, pk=None):
        question = Question.objects.filter(pk=pk).first()
        token = request.query_params.get("token")
        if (
            question is None
            or question.demo_token is None
            or token != str(question.demo_token)
        ):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            QuestionSerializer(question, context=self.get_serializer_context()).data
        )


class ThreadViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Thread.objects.all()
    serializer_class = ThreadSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def retrieve(self, request, pk=None):
        thread = self.get_object()
        payload = ThreadSerializer(thread, context=self.get_serializer_context()).data
        payload["questions"] = QuestionSerializer(
            thread.questions.all(), many=True, context=self.get_serializer_context()
        ).data
        return Response(payload)