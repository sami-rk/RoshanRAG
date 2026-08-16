from functools import lru_cache

from django.conf import settings
from langchain_openrouter import ChatOpenRouter


def _model(model_name: str) -> ChatOpenRouter:
    return ChatOpenRouter(
        model=model_name,
        api_key=settings.OPENROUTER_API_KEY,
        temperature=0.2,
        timeout=90,
        max_retries=1,
    )


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenRouter:
    primary = _model(settings.LLM_MODEL)
    fallbacks = [_model(model.strip()) for model in settings.LLM_FALLBACK_MODELS if model.strip()]
    return primary.with_fallbacks(fallbacks)