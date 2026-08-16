"""
Django settings for the RoshanRAG project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


SECRET_KEY = env("SECRET_KEY", "django-insecure-dev-key")
DEBUG = env("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "*").split(",")

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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
MEDIA_URL = "media/"
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))

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
    "deepseek/deepseek-chat:free,qwen/qwen-2.5-72b-instruct:free",
).split(",")

EMBEDDING_MODEL = env("EMBEDDING_MODEL", "BAAI/bge-m3")
CHROMA_HOST = env("CHROMA_HOST", "localhost")
CHROMA_PORT = int(env("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = env("CHROMA_COLLECTION", "roshan_documents")

CHUNK_SIZE = int(env("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(env("CHUNK_OVERLAP", "200"))
RETRIEVAL_TOP_K = int(env("RETRIEVAL_TOP_K", "4"))
RETRIEVAL_MAX_DOCS = int(env("RETRIEVAL_MAX_DOCS", "3"))

MAX_UPLOAD_SIZE_MB = int(env("MAX_UPLOAD_SIZE_MB", "25"))