import json
import logging
from functools import lru_cache

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
    "برای هر ادعایی که از یک سند گرفته می‌شود، شماره آن سند را به صورت [1] یا [2] همان‌جا درون متن بیاور؛ "
    "شماره‌ها با ترتیب اسناد در فهرست «منابع» یکی است. "
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


@lru_cache(maxsize=1)
def _get_reranker():
    model_name = getattr(settings, "RERANKER_MODEL", "")
    if not model_name:
        return None
    try:
        import torch

        from sentence_transformers import CrossEncoder

        device = "cuda" if torch.cuda.is_available() else "cpu"
        return CrossEncoder(model_name, device=device, trust_remote_code=True)
    except Exception as exc:  # pragma: no cover - depends on optional model download
        logger.warning("Failed to load reranker %s: %s", model_name, exc)
        return None


def _rerank(query: str, documents):
    reranker = _get_reranker()
    if reranker is None or not documents:
        return documents
    try:
        pairs = [(query, doc.page_content) for doc in documents]
        scores = reranker.predict(pairs)
        # CrossEncoder returns numpy array or list; sort descending
        ranked = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]
    except Exception as exc:  # pragma: no cover - graceful fallback
        logger.warning("Reranking failed, using vector order: %s", exc)
        return documents


def _build_retrieval_query(question) -> str:
    """Build a retrieval query that includes recent thread history.

    For follow-up questions the thread contains prior Q/A that disambiguates
    pronouns and topic. The last two turns are prepended in chronological
    order, keeping the current question verbatim at the end so the embedding
    stays centered on the user intent.
    """
    base = question.question or ""
    if not question.thread_id:
        return base
    # Last two completed turns in this thread, oldest first
    try:
        previous = list(
            Question.objects.filter(thread_id=question.thread_id)
            .exclude(pk=question.pk)
            .order_by("-created_at")[:2]
        )
    except Exception:
        return base
    if not previous:
        return base
    previous.reverse()
    parts = []
    for prev in previous:
        if prev.question:
            parts.append(f"پرسش قبلی: {prev.question}")
        if prev.answer:
            # Keep answer short to avoid drowning the embedding
            parts.append(f"پاسخ قبلی: {prev.answer[:400]}")
    if not parts:
        return base
    return "\n".join(parts) + f"\nپرسش فعلی: {base}"


def _coerce_answer_content(content) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


def _stream_answer(llm, messages, question):
    """Invoke the model, streaming tokens into ``question.stream_data``.

    Returns the full answer text. If the provider does not support streaming,
    falls back to a single ``invoke`` call whose whole answer is flushed at once.
    """
    answer_parts = []
    last_flush = 0
    try:
        for chunk in llm.stream(messages):
            text = _coerce_answer_content(getattr(chunk, "content", chunk))
            if not text:
                continue
            answer_parts.append(text)
            question.stream_data += text
            if len(question.stream_data) - last_flush >= 150:
                last_flush = len(question.stream_data)
                Question.objects.filter(pk=question.pk).update(
                    stream_data=question.stream_data
                )
        return "".join(answer_parts)
    except Exception:
        response = llm.invoke(messages)
        answer = _coerce_answer_content(response.content)
        question.stream_data = answer
        Question.objects.filter(pk=question.pk).update(stream_data=answer)
        return answer


def _build_sources(retrieved):
    # Bulk-fetch file URLs so sources can deep-link to the protected media
    # endpoint; existing vector chunks without file_url fall back to the DB.
    doc_ids = [d.metadata.get("document_id") for d in retrieved]
    db_docs = {
        doc.pk: doc
        for doc in Document.objects.filter(pk__in=[i for i in doc_ids if i is not None])
    }
    sources = []
    for index, document in enumerate(retrieved, start=1):
        doc_id = document.metadata.get("document_id")
        file_url = document.metadata.get("file_url")
        if not file_url and doc_id in db_docs:
            db_doc = db_docs[doc_id]
            if db_doc.file:
                try:
                    file_url = db_doc.file.url
                except Exception:
                    file_url = None
        sources.append(
            {
                "document_id": doc_id,
                "title": document.metadata.get("title"),
                "excerpt": document.page_content[:300],
                "citation": index,
                "file_url": file_url,
            }
        )
    return sources


def answer_question(question_id: int) -> None:
    question = Question.objects.filter(pk=question_id).first()
    if question is None:
        return
    if question.status == Question.Status.GENERATING:
        # A worker is already producing an answer for this question. Skipping
        # here makes the admin re-answer action safe to click repeatedly
        # without double-invoking the LLM.
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
            # For thread-aware retrieval the query is expanded with the last two
            # turns so follow-up pronouns ("آن"، "this") resolve correctly.
            retrieval_query = _build_retrieval_query(question)
            # MMR (maximal marginal relevance) balances relevance with diversity so
            # the retrieved chunks cover different parts of the documents instead of
            # near-duplicate passages.
            retrieved = vectorstore.max_marginal_relevance_search(
                retrieval_query,
                k=settings.RETRIEVAL_TOP_K,
                fetch_k=settings.RETRIEVAL_FETCH_K,
            )
            # Optional cross-encoder reranking sharpens MMR results when a
            # reranker model is configured; falls back to vector order on error
            # or when disabled.
            retrieved = _rerank(retrieval_query, retrieved)
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
                response = get_llm()

                answer = _stream_answer(response, messages, question)

                question.answer = answer
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
            update_fields=[
                "answer",
                "sources",
                "status",
                "answered_at",
                "error_message",
                "stream_data",
            ]
        )


def schedule_answering(question_id: int) -> None:
    def mark_failed(exc: Exception) -> None:
        # The answering worker crashed before it could finish; record that so
        # the question is not left stuck in pending/generating forever.
        if Question.objects.filter(pk=question_id).exists():
            Question.objects.filter(pk=question_id).update(
                status=Question.Status.FAILED,
                error_message=friendly_llm_error(exc),
            )

    run_in_background(answer_question, question_id, on_error=mark_failed)
