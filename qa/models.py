from django.db import models


class Question(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        GENERATING = "generating", "در حال تولید"
        DONE = "done", "پاسخ داده شده"
        FAILED = "failed", "ناموفق"

    question = models.TextField("پرسش")
    answer = models.TextField("پاسخ", blank=True, default="")
    status = models.CharField(
        "وضعیت", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    sources = models.JSONField("منابع", default=list, blank=True)
    error_message = models.TextField("پیام خطا", blank=True, default="")
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    answered_at = models.DateTimeField("تاریخ پاسخ", null=True, blank=True)

    class Meta:
        verbose_name = "پرسش"
        verbose_name_plural = "پرسش‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.question[:50]