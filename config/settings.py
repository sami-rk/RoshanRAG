"""
Django settings for the RoshanRAG project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


SECRET_KEY = env("SECRET_KEY", "django-insecure-dev-key")
DEBUG = env("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "*").split(",")

# Refuse to boot in production with a placeholder secret. The README documents
# DEBUG=true and the dev secret as local-development-only, so this fails fast
# instead of silently running on an easily guessable signing key.
_INSECURE_SECRET_KEYS = {
    "django-insecure-dev-key",
    "dev-secret-key",
    "change-me",
    "change-me-to-a-long-random-string",
    "your-secret-key-here",
    "secret",
}
if not DEBUG and (
    not SECRET_KEY
    or SECRET_KEY in _INSECURE_SECRET_KEYS
    or SECRET_KEY.startswith("django-insecure-")
):
    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a strong random value when DEBUG is disabled"
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "core",
    "documents",
    "qa",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

try:
    import whitenoise  # noqa: F401
except ImportError:
    pass
else:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "fa-ir"
LANGUAGES = [
    ("fa", "فارسی"),
    ("en", "English"),
]
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    # The manifest storage hashes filenames for cache-busting, but it needs a
    # `collectstatic`-generated manifest to resolve {% static %} tags. Use it
    # only in production; development and tests fall back to the plain storage
    # so a fresh checkout works without running collectstatic first.
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": env("THROTTLE_USER_RATE", "300/minute"),
        "anon": env("THROTTLE_ANON_RATE", "30/minute"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RoshanRAG API",
    "DESCRIPTION": (
        "سامانه پرسش از اسناد (RoshanRAG) — ثبت و مدیریت اسناد متنی، جست‌وجو در اسناد "
        "و پاسخ به پرسش کاربران بر اساس محتوای اسناد با استفاده از RAG و مدل زبانی."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", "")
LLM_MODEL = env("LLM_MODEL", "poolside/laguna-s-2.1:free")
LLM_FALLBACK_MODELS = env(
    "LLM_FALLBACK_MODELS",
    "openai/gpt-oss-20b:free,nvidia/nemotron-nano-9b-v2:free",
).split(",")

EMBEDDING_MODEL = env("EMBEDDING_MODEL", "BAAI/bge-m3")
CHROMA_HOST = env("CHROMA_HOST", "localhost")
CHROMA_PORT = int(env("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = env("CHROMA_COLLECTION", "roshan_documents")

CHUNK_SIZE = int(env("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(env("CHUNK_OVERLAP", "200"))
RETRIEVAL_TOP_K = int(env("RETRIEVAL_TOP_K", "4"))
RETRIEVAL_FETCH_K = int(env("RETRIEVAL_FETCH_K", "20"))
RETRIEVAL_MAX_DOCS = int(env("RETRIEVAL_MAX_DOCS", "3"))

MAX_UPLOAD_SIZE_MB = int(env("MAX_UPLOAD_SIZE_MB", "25"))