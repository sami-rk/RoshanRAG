import json
import logging

from django.conf import settings
from django.utils import timezone
from langchain_core.messages import HumanMessage, SystemMessage

from core.chroma_client import get_chroma_vectorstore
from core.llm_client import get_llm
from core.workers import run_in_background
from documents.models import Document
from qa.models import Question

logger = logging.getLogger(__name__)


def friendly_llm_error(exc: Exception) -> str:
    """Extract a human-readable message from LLM/HTTP client exceptions.

    Provider SDKs (OpenRouter/OpenAI) wrap the actual error — e.g. an HTTP 403
    "Access denied by security policy." — inside pydantic validation errors or
    JSON-string bodies. This digs out the real message so admins see the cause
    instead of an SDK unmarshalling dump.
    """
    # openrouter / openai style: body is a JSON string like
    # '{ "success": false, "error": "Access denied by security policy." }'
    body = getattr(exc, "body", None)
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            body = parsed
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str) and error:
            return error

    # pydantic ValidationError (some SDK versions raise it directly)
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            for err in errors():
                value = err.get("input_value")
                if isinstance(value, str) and value:
                    return value
        except Exception:
            pass

    message = getattr(exc, "message", None)
    if isinstance(message, str) and message and "validation error" not in message.lower():
        return message

    return str(exc)

_SYSTEM_PROMPT = (
    "تو دستیار پاسخ‌دهی بر اساس اسناد (RoshanRAG) هستی. "
    "فقط بر اساس متن‌های داخل بخش «اسناد» پاسخ بده و از دانش عمومی خارجی استفاده نکن. "
    "اگر پاسخ پرسش در اسناد موجود نیست، صراحتاً بگو که اطلاعات کافی در اسناد وجود ندارد. "
    "به همان زبانی پاسخ بده که پرسش کاربر با آن زبان نوشته شده است. "
    "در پایان پاسخ، فهرست «منابع:» را با عنوان اسناد استفاده‌شده بیاور."
)


def _dedupe_by_document(documents, max_docs):
    seen = set()
    result = []
    for document in documents:
        document_id = document.metadata.get("document_id")
        if document_id in seen:
            continue
        seen.add(document_id)
        result.append(document)
        if len(result) >= max_docs:
            break
    return result


def _coerce_answer_content(content) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


def _build_sources(retrieved):
    sources = []
    for document in retrieved:
        sources.append(
            {
                "document_id": document.metadata.get("document_id"),
                "title": document.metadata.get("title"),
                "excerpt": document.page_content[:300],
            }
        )
    return sources


def answer_question(question_id: int) -> None:
    question = Question.objects.filter(pk=question_id).first()
    if question is None:
        return
    try:
        question.status = Question.Status.GENERATING
        question.save(update_fields=["status"])

        if not Document.objects.filter(status=Document.Status.READY).exists():
            # There is nothing to retrieve or ground the answer on, so skip the
            # LLM call entirely and answer with a clear, deterministic message.
            question.answer = (
                "هنوز سندی برای پاسخ‌دهی ایندکس نشده است؛ ابتدا یک سند بارگذاری کنید."
            )
            question.status = Question.Status.DONE
            question.answered_at = timezone.now()
            question.error_message = ""
        else:
            vectorstore = get_chroma_vectorstore()
            # MMR (maximal marginal relevance) balances relevance with diversity so
            # the retrieved chunks cover different parts of the documents instead of
            # near-duplicate passages.
            retrieved = vectorstore.max_marginal_relevance_search(
                question.question,
                k=settings.RETRIEVAL_TOP_K,
                fetch_k=settings.RETRIEVAL_FETCH_K,
            )
            retrieved = _dedupe_by_document(retrieved, settings.RETRIEVAL_MAX_DOCS)

            if not retrieved:
                question.answer = (
                    "در اسناد موجود محتوایی مرتبط با پرسش شما یافت نشد."
                )
                question.sources = []
                question.status = Question.Status.DONE
                question.answered_at = timezone.now()
                question.error_message = ""
            else:
                context = "\n\n".join(document.page_content for document in retrieved)
                messages = [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(content=f"پرسش:\n{question.question}\n\nاسناد:\n{context}"),
                ]
                response = get_llm().invoke(messages)

                question.answer = _coerce_answer_content(response.content)
                question.sources = _build_sources(retrieved)
                question.status = Question.Status.DONE
                question.answered_at = timezone.now()
                question.error_message = ""
    except Exception as exc:
        question.status = Question.Status.FAILED
        question.error_message = friendly_llm_error(exc)
        logger.exception("Failed to answer question %s", question_id)

    # The question may have been deleted while the LLM call was in flight.
    if Question.objects.filter(pk=question.pk).exists():
        question.save(
            update_fields=["answer", "sources", "status", "answered_at", "error_message"]
        )


def schedule_answering(question_id: int) -> None:
    run_in_background(answer_question, question_id)