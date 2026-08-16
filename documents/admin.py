from django.contrib import admin
from django.utils.html import format_html

from core.admin_site import roshan_admin_site
from .models import Document

STATUS_PILLS = {
    Document.Status.READY: "pill-ready",
    Document.Status.PENDING: "pill-pending",
    Document.Status.FAILED: "pill-failed",
}


class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "status_badge", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "full_text")
    readonly_fields = ("status", "error_message", "full_text", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "file")}),
        ("پردازش", {"fields": ("status", "error_message")}),
        ("متن کامل", {"fields": ("full_text",)}),
        ("زمان", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="وضعیت", ordering="status")
    def status_badge(self, obj):
        pill_class = STATUS_PILLS.get(obj.status, "pill-pending")
        return format_html('<span class="pill {}">{}</span>', pill_class, obj.get_status_display())


roshan_admin_site.register(Document, DocumentAdmin)