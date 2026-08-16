from django.contrib import admin

from documents.models import Document
from qa.models import Question


class RoshanAdminSite(admin.AdminSite):
    site_header = "روشن RAG"
    site_title = "روشن RAG"
    index_title = "پنل مدیریت"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        documents = Document.objects.all()
        questions = Question.objects.all()
        extra_context["stats"] = {
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
        return super().index(request, extra_context=extra_context)


roshan_admin_site = RoshanAdminSite(name="admin")