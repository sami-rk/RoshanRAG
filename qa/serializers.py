from rest_framework import serializers

from .models import Question, Thread


class QuestionSerializer(serializers.ModelSerializer):
    thread = serializers.PrimaryKeyRelatedField(
        queryset=Thread.objects.all(), required=False, allow_null=True
    )

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
            "thread",
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

    def update(self, instance, validated_data):
        # Only feedback can change once a question exists.
        if "feedback" in validated_data:
            instance.feedback = validated_data["feedback"]
            instance.save(update_fields=["feedback"])
        return instance


class ThreadSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = ["id", "title", "question_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_question_count(self, obj):
        return obj.questions.count()