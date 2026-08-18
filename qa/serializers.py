from rest_framework import serializers

from .models import Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "question",
            "answer",
            "status",
            "feedback",
            "sources",
            "error_message",
            "created_at",
            "answered_at",
        ]
        read_only_fields = [
            "id",
            "answer",
            "status",
            "sources",
            "error_message",
            "created_at",
            "answered_at",
        ]