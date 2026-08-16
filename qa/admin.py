from django.contrib import admin

from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question", "status", "created_at", "answered_at")
    list_filter = ("status", "created_at")
    search_fields = ("question", "answer")
    readonly_fields = ("status", "error_message", "sources", "created_at", "answered_at")
    fieldsets = (
        ("پرسش", {"fields": ("question",)}),
        ("پاسخ", {"fields": ("answer", "sources")}),
        ("وضعیت", {"fields": ("status", "error_message")}),
        ("زمان", {"fields": ("created_at", "answered_at")}),
    )