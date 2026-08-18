from django.contrib import admin
from django.urls import path

from core.stats import get_analytics_context, get_dashboard_stats


class RoshanAdminSite(admin.AdminSite):
    site_header = "روشن RAG"
    site_title = "روشن RAG"
    index_title = "پنل مدیریت"
    site_url = "/"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["stats"] = get_dashboard_stats()
        return super().index(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "analytics/",
                self.admin_view(self.analytics_view),
                name="analytics",
            ),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        from django.shortcuts import render

        context = self.each_context(request)
        context["analytics"] = get_analytics_context()
        context["title"] = "داشبورد تحلیلی"
        return render(request, "admin/analytics.html", context)


roshan_admin_site = RoshanAdminSite(name="admin")