from functools import lru_cache

import chromadb
from django.conf import settings
from langchain_chroma import Chroma

from .embeddings import get_embeddings


@lru_cache(maxsize=1)
def _get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


@lru_cache(maxsize=1)
def get_chroma_collection():
    return _get_client().get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


@lru_cache(maxsize=1)
def get_chroma_vectorstore() -> Chroma:
    return Chroma(
        client=_get_client(),
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
    )


def delete_document_chunks(document_id: int) -> None:
    collection = get_chroma_collection()
    existing = collection.get(where={"document_id": document_id})
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)