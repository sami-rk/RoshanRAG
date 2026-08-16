from pathlib import Path

from rest_framework import serializers

from .models import Document

SUPPORTED_EXTENSIONS = {"docx", "txt"}


class DocumentSerializer(serializers.ModelSerializer):
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
            raise serializers.ValidationError("فرمت فایل باید docx یا txt باشد")
        return value

    def create(self, validated_data):
        title = validated_data.pop("title", None)
        if not title:
            title = Path(validated_data["file"].name).stem
        return Document.objects.create(title=title, **validated_data)