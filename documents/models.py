from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        READY = "ready", "آماده"
        FAILED = "failed", "ناموفق"

    title = models.CharField("عنوان", max_length=255)
    file = models.FileField("فایل", upload_to="documents/%Y/%m/")
    full_text = models.TextField("متن کامل", blank=True, default="")
    status = models.CharField(
        "وضعیت", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField("پیام خطا", blank=True, default="")
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("تاریخ به‌روزرسانی", auto_now=True)

    class Meta:
        verbose_name = "سند"
        verbose_name_plural = "اسناد"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def file_extension(self):
        name = self.file.name.lower() if self.file else ""
        return name.rsplit(".", 1)[-1] if "." in name else ""