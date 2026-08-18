from django.contrib import admin
from django.contrib.admin import actions as admin_actions
from django.utils.html import format_html

from core.admin_site import roshan_admin_site
from .models import Question
from .services.answering import schedule_answering

STATUS_PILLS = {
    Question.Status.DONE: "pill-done",
    Question.Status.PENDING: "pill-pending",
    Question.Status.GENERATING: "pill-generating",
    Question.Status.FAILED: "pill-failed",
}


class QuestionAdmin(admin.ModelAdmin):
    actions = ("delete_selected", "retry_answering")
    list_display = ("question", "status_badge", "feedback_badge", "created_at", "answered_at")
    list_filter = ("status", "feedback", "created_at")
    search_fields = ("question", "answer")
    readonly_fields = ("status", "error_message", "sources", "created_at", "answered_at")
    fieldsets = (
        ("پرسش", {"fields": ("question",)}),
        ("پاسخ", {"fields": ("answer", "sources")}),
        ("بازخورد", {"fields": ("feedback",)}),
        ("وضعیت", {"fields": ("status", "error_message")}),
        ("زمان", {"fields": ("created_at", "answered_at")}),
    )

    @admin.display(description="وضعیت", ordering="status")
    def status_badge(self, obj):
        pill_class = STATUS_PILLS.get(obj.status, "pill-pending")
        return format_html('<span class="pill {}">{}</span>', pill_class, obj.get_status_display())

    @admin.display(description="بازخورد", ordering="feedback")
    def feedback_badge(self, obj):
        if obj.feedback == Question.Feedback.UP:
            pill_class = "pill-ready"
        elif obj.feedback == Question.Feedback.DOWN:
            pill_class = "pill-failed"
        else:
            return "—"
        return format_html('<span class="pill {}">{}</span>', pill_class, obj.get_feedback_display())

    def delete_selected(self, request, queryset):
        return admin_actions.delete_selected(self, request, queryset)

    delete_selected.short_description = "حذف پرسش‌های انتخاب‌شده"
    delete_selected.allowed_permissions = ("delete",)

    def retry_answering(self, request, queryset):
        count = 0
        for question in queryset:
            schedule_answering(question.pk)
            count += 1
        self.message_user(request, f"پاسخ‌دهی مجدد {count} پرسش در پس‌زمینه آغاز شد")

    retry_answering.short_description = "پاسخ‌دهی مجدد پرسش‌های انتخاب‌شده"
    retry_answering.allowed_permissions = ("change",)


roshan_admin_site.register(Question, QuestionAdmin)