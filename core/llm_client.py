from functools import lru_cache

from django.conf import settings
from langchain_openrouter import ChatOpenRouter


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenRouter:
    primary = ChatOpenRouter(
        model=settings.LLM_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        temperature=0.2,
        timeout=120,
    )
    fallbacks = [
        ChatOpenRouter(
            model=model.strip(),
            api_key=settings.OPENROUTER_API_KEY,
            temperature=0.2,
            timeout=120,
        )
        for model in settings.LLM_FALLBACK_MODELS
        if model.strip()
    ]
    return primary.with_fallbacks(fallbacks)