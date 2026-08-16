import logging

from django.conf import settings
from django.utils import timezone
from langchain_core.messages import HumanMessage, SystemMessage

from core.chroma_client import get_chroma_vectorstore
from core.llm_client import get_llm
from core.workers import run_in_background
from qa.models import Question

logger = logging.getLogger(__name__)

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
        question.save(update_fields=["status", "updated_at"])

        vectorstore = get_chroma_vectorstore()
        retrieved = vectorstore.similarity_search(
            question.question,
            k=settings.RETRIEVAL_TOP_K,
        )
        retrieved = _dedupe_by_document(retrieved, settings.RETRIEVAL_MAX_DOCS)

        context = "\n\n".join(document.page_content for document in retrieved)
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"پرسش:\n{question.question}\n\nاسناد:\n{context}"),
        ]
        response = get_llm().invoke(messages)

        question.answer = response.content
        question.sources = _build_sources(retrieved)
        question.status = Question.Status.DONE
        question.answered_at = timezone.now()
        question.error_message = ""
    except Exception as exc:
        question.status = Question.Status.FAILED
        question.error_message = str(exc)
        logger.exception("Failed to answer question %s", question_id)

    question.save()


def schedule_answering(question_id: int) -> None:
    run_in_background(answer_question, question_id)