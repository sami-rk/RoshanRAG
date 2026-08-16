from django.contrib import admin
from django.utils.html import format_html

from core.admin_site import roshan_admin_site
from .models import Question

STATUS_PILLS = {
    Question.Status.DONE: "pill-done",
    Question.Status.PENDING: "pill-pending",
    Question.Status.GENERATING: "pill-generating",
    Question.Status.FAILED: "pill-failed",
}


class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question", "status_badge", "created_at", "answered_at")
    list_filter = ("status", "created_at")
    search_fields = ("question", "answer")
    readonly_fields = ("status", "error_message", "sources", "created_at", "answered_at")
    fieldsets = (
        ("پرسش", {"fields": ("question",)}),
        ("پاسخ", {"fields": ("answer", "sources")}),
        ("وضعیت", {"fields": ("status", "error_message")}),
        ("زمان", {"fields": ("created_at", "answered_at")}),
    )

    @admin.display(description="وضعیت", ordering="status")
    def status_badge(self, obj):
        pill_class = STATUS_PILLS.get(obj.status, "pill-pending")
        return format_html('<span class="pill {}">{}</span>', pill_class, obj.get_status_display())


roshan_admin_site.register(Question, QuestionAdmin)