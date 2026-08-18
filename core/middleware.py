from django.conf import settings


class ForceDefaultLanguageMiddleware:
    """Seed the language cookie to the project default so browsers that send an
    English Accept-Language header still get Persian until the visitor toggles."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.LANGUAGE_COOKIE_NAME not in request.COOKIES:
            request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = settings.LANGUAGE_CODE
        return self.get_response(request)