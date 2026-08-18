import uuid

from django.db import models


class Thread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("عنوان", max_length=200, blank=True, default="")
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("تاریخ به‌روزرسانی", auto_now=True)

    class Meta:
        verbose_name = "گفتگو"
        verbose_name_plural = "گفتگوها"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or "گفتگوی بی‌عنوان"


class Question(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        GENERATING = "generating", "در حال تولید"
        DONE = "done", "پاسخ داده شده"
        FAILED = "failed", "ناموفق"

    class Feedback(models.TextChoices):
        NONE = "none", "بدون بازخورد"
        UP = "up", "پاسخ مفید بود"
        DOWN = "down", "پاسخ مفید نبود"

    question = models.TextField("پرسش")
    answer = models.TextField("پاسخ", blank=True, default="")
    thread = models.ForeignKey(
        Thread,
        verbose_name="گفتگو",
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,
        blank=True,
    )
    stream_data = models.TextField("متن در حال تولید", blank=True, default="")
    status = models.CharField(
        "وضعیت", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    feedback = models.CharField(
        "بازخورد", max_length=4, choices=Feedback.choices, default=Feedback.NONE
    )
    sources = models.JSONField("منابع", default=list, blank=True)
    error_message = models.TextField("پیام خطا", blank=True, default="")
    demo_token = models.UUIDField(
        "شناسه دمو", null=True, blank=True, unique=True, editable=False
    )
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    answered_at = models.DateTimeField("تاریخ پاسخ", null=True, blank=True)

    class Meta:
        verbose_name = "پرسش"
        verbose_name_plural = "پرسش‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.question[:50]