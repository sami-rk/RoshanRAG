from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.static import serve

from core.stats import get_dashboard_stats


def protected_media(request, path):
    """Serve uploaded document files only to authenticated clients.

    Admin sessions are already authenticated by the normal middleware. API
    consumers pass the same ``Authorization: Token <key>`` header they use for
    the JSON endpoints, so file URLs from the API keep working for them while
    the files stay unavailable to anonymous visitors who only know the URL.
    """
    user = request.user if request.user.is_authenticated else None
    if user is None or not user.is_active:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Token "):
            from rest_framework.authtoken.models import Token

            parts = header.split(" ")
            if len(parts) == 2:
                token = (
                    Token.objects.select_related("user")
                    .filter(key=parts[1], user__is_active=True)
                    .first()
                )
                if token is not None:
                    user = token.user
    if user is None:
        raise PermissionDenied

    return serve(request, path, document_root=settings.MEDIA_ROOT)


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def health_check(request):
    """Lightweight health endpoint for container healthchecks and uptime probes.

    Verifies the database connection and Chroma reachability, returning 503
    while any dependency is unavailable so orchestrators can restart the service.
    """
    try:
        connection.ensure_connection()
        database_ok = True
    except Exception:
        database_ok = False

    try:
        from core.chroma_client import _get_client

        _get_client().heartbeat()
        chroma_ok = True
    except Exception:
        chroma_ok = False

    if database_ok and chroma_ok:
        return JsonResponse({"status": "ok", "database": "ok", "chroma": "ok"})
    return JsonResponse(
        {
            "status": "error",
            "database": "ok" if database_ok else "unreachable",
            "chroma": "ok" if chroma_ok else "unreachable",
        },
        status=503,
    )


class PublicContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = get_dashboard_stats()
        return context


class LandingView(PublicContextMixin, TemplateView):
    template_name = "landing/home.html"


class AboutView(PublicContextMixin, TemplateView):
    template_name = "landing/about.html"


class PricingView(PublicContextMixin, TemplateView):
    template_name = "landing/pricing.html"


class ContactView(PublicContextMixin, TemplateView):
    template_name = "landing/contact.html"


class ChatView(PublicContextMixin, TemplateView):
    template_name = "landing/chat.html"
