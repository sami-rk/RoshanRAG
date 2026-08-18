from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(full_text__icontains=query))
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @action(detail=False, methods=["post"])
    def batch(self, request):
        uploads = request.FILES.getlist("files")
        if not uploads:
            return Response(
                {"detail": "هیچ فایلی ارسال نشده است."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = []
        errors = []
        for upload in uploads:
            serializer = DocumentSerializer(
                data={"file": upload}, context=self.get_serializer_context()
            )
            if serializer.is_valid():
                created.append(
                    DocumentSerializer(
                        serializer.save(), context=self.get_serializer_context()
                    ).data
                )
            else:
                errors.append({"file": upload.name, "errors": serializer.errors})
        response_status = (
            status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST
        )
        return Response({"created": created, "errors": errors}, status=response_status)