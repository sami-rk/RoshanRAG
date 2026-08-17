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
