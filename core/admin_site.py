from django.contrib import admin

from core.stats import get_dashboard_stats


class RoshanAdminSite(admin.AdminSite):
    site_header = "روشن RAG"
    site_title = "روشن RAG"
    index_title = "پنل مدیریت"
    site_url = "/"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["stats"] = get_dashboard_stats()
        return super().index(request, extra_context=extra_context)


roshan_admin_site = RoshanAdminSite(name="admin")