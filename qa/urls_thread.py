from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ThreadViewSet

thread_router = DefaultRouter()
thread_router.register("", ThreadViewSet, basename="thread")

urlpatterns = [
    path("", include(thread_router.urls)),
]