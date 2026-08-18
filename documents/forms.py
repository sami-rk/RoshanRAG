from django import forms
from django.conf import settings

from .models import Document
from .serializers import SUPPORTED_EXTENSIONS
from .validation import validate_upload_file


class DocumentAdminForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = "__all__"

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if not file:
            return file
        extension = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
        if extension not in SUPPORTED_EXTENSIONS:
            raise forms.ValidationError("فرمت فایل باید docx، pdf یا txt باشد")
        if file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"حجم فایل نباید بیشتر از {settings.MAX_UPLOAD_SIZE_MB} مگابایت باشد"
            )
        error = validate_upload_file(file)
        if error:
            raise forms.ValidationError(error)
        return file