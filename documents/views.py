from django.db.models import Q
from rest_framework import viewsets

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