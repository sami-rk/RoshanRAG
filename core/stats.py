from datetime import timedelta
from collections import Counter

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from documents.models import Document
from qa.models import Question


def get_dashboard_stats():
    documents = Document.objects.all()
    questions = Question.objects.all()
    return {
        "documents": documents.count(),
        "documents_ready": documents.filter(status=Document.Status.READY).count(),
        "documents_pending": documents.filter(status=Document.Status.PENDING).count(),
        "documents_failed": documents.filter(status=Document.Status.FAILED).count(),
        "questions": questions.count(),
        "questions_done": questions.filter(status=Question.Status.DONE).count(),
        "questions_generating": questions.filter(
            status=Question.Status.GENERATING
        ).count(),
        "questions_pending": questions.filter(status=Question.Status.PENDING).count(),
        "questions_failed": questions.filter(status=Question.Status.FAILED).count(),
    }


def get_questions_per_day(days=30):
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        Question.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
    )
    by_day = {row["day"]: row["count"] for row in rows}
    return [
        {"date": (start + timedelta(days=offset)).isoformat(), "count": by_day.get(start + timedelta(days=offset), 0)}
        for offset in range(days)
    ]


def get_feedback_counts():
    counts = {"up": 0, "down": 0, "none": 0}
    for row in Question.objects.values("feedback").annotate(count=Count("id")):
        if row["feedback"] in counts:
            counts[row["feedback"]] = row["count"]
    return counts


def get_top_documents(limit=5):
    usage = Counter()
    for sources in Question.objects.exclude(sources=[]).values_list("sources", flat=True):
        for source in sources or []:
            doc_id = source.get("document_id")
            if doc_id is not None:
                usage[doc_id] += 1
    top_ids = [doc_id for doc_id, _ in usage.most_common(limit)]
    titles = dict(Document.objects.filter(pk__in=top_ids).values_list("pk", "title"))
    return [
        {"title": titles.get(doc_id, "(حذف‌شده)"), "uses": usage[doc_id]}
        for doc_id in top_ids
    ]


def get_analytics_context():
    context = get_dashboard_stats()
    context.update(
        {
            "questions_per_day": get_questions_per_day(),
            "feedback_counts": get_feedback_counts(),
            "top_documents": get_top_documents(),
        }
    )
    return context
