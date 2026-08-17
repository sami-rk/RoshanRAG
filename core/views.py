from django.views.generic import TemplateView

from core.stats import get_dashboard_stats


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
