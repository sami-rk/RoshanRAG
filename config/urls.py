from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

from core.admin_site import roshan_admin_site
from core.views import (
    AboutView,
    ChatView,
    ContactView,
    LandingView,
    PricingView,
    health_check,
    protected_media,
)

handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"

urlpatterns = [
    path("", LandingView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("pricing/", PricingView.as_view(), name="pricing"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("chat/", ChatView.as_view(), name="chat"),
    path("admin/", roshan_admin_site.urls),
    path("api/token/", obtain_auth_token, name="api-token"),
    path("api/health/", health_check, name="health"),
    path("api/documents/", include("documents.urls")),
    path("api/questions/", include("qa.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="schema-docs",
    ),
]

# Serve uploaded media in all environments (DEBUG-independent) so document
# files remain accessible behind gunicorn with DEBUG=false — gated behind a
# session or API-token check.
urlpatterns += [
    path(
        f"{settings.MEDIA_URL.lstrip('/')}<path:path>",
        protected_media,
        name="protected_media",
    ),
]