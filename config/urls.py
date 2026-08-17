from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

from core.admin_site import roshan_admin_site
from core.views import AboutView, ContactView, LandingView, PricingView

handler404 = "core.views.page_not_found"

urlpatterns = [
    path("", LandingView.as_view(), name="home"),
    path("about/", AboutView.as_view(), name="about"),
    path("pricing/", PricingView.as_view(), name="pricing"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("admin/", roshan_admin_site.urls),
    path("api/token/", obtain_auth_token, name="api-token"),
    path("api/documents/", include("documents.urls")),
    path("api/questions/", include("qa.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="schema-docs",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)