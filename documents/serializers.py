from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import Document

SUPPORTED_EXTENSIONS = {"docx", "pdf", "txt"}


class DocumentSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "full_text",
            "status",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_text", "status", "error_message", "created_at", "updated_at"]

    def validate_file(self, value):
        extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if extension not in SUPPORTED_EXTENSIONS:
            raise serializers.ValidationError("فرمت فایل باید docx، pdf یا txt باشد")
        if value.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"حجم فایل نباید بیشتر از {settings.MAX_UPLOAD_SIZE_MB} مگابایت باشد"
            )
        return value

    def create(self, validated_data):
        title = validated_data.pop("title", None)
        if not title:
            title = Path(validated_data["file"].name).stem
        return Document.objects.create(title=title, **validated_data)