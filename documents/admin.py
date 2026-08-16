from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "full_text")
    readonly_fields = ("status", "error_message", "full_text", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("title", "file")}),
        ("پردازش", {"fields": ("status", "error_message")}),
        ("متن کامل", {"fields": ("full_text",)}),
        ("زمان", {"fields": ("created_at", "updated_at")}),
    )