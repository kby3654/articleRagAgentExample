"""Chroma 벡터 DB 클라이언트 — 적재(upsert) 및 검색."""

from __future__ import annotations

import os

# chromadb 텔레메트리(posthog) 비활성화 — import 전 설정
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY", "False")

import chromadb
from chromadb import Collection
from langchain_huggingface import HuggingFaceEmbeddings

_client: chromadb.PersistentClient | None = None
_collection: Collection | None = None
_embedder: HuggingFaceEmbeddings | None = None


def _get_collection() -> Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    chroma_path = os.getenv("CHROMA_PATH", "./data/chroma")
    collection_name = os.getenv("CHROMA_COLLECTION", "law_statutes")

    _client = chromadb.PersistentClient(
        path=chroma_path,
        settings=chromadb.Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def get_embedder() -> HuggingFaceEmbeddings:
    global _embedder
    if _embedder is not None:
        return _embedder
    model_name = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
    _embedder = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return _embedder


def upsert_articles(articles: list) -> int:
    """Article 리스트를 Chroma에 upsert. 반환: 처리 건수."""

    col = _get_collection()
    embedder = get_embedder()

    texts = [a.text for a in articles]
    # chunk_id 중복 방지: 동일 ID 발생 시 순번 suffix 부여
    ids = []
    seen: dict[str, int] = {}
    for a in articles:
        cid = a.chunk_id
        if cid in seen:
            seen[cid] += 1
            cid = f"{cid}#{seen[cid]}"
        else:
            seen[cid] = 0
        ids.append(cid)
    metadatas = [
        {
            "law_name": a.law_name,
            "law_id": a.law_id,
            "article_no": a.article_no,
            "paragraph_no": a.paragraph_no,
            "article_title": a.article_title,
            "enforcement_date": a.enforcement_date,
            "source_url": a.source_url,
        }
        for a in articles
    ]

    embeddings = embedder.embed_documents(texts)

    col.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(articles)


def search(query: str, k: int = 5, law_name: str | None = None) -> list[dict]:
    """벡터 유사도 검색. law_name 지정 시 해당 법령으로 필터."""
    col = _get_collection()
    embedder = get_embedder()

    query_vec = embedder.embed_query(query)
    where = {"law_name": {"$eq": law_name}} if law_name else None

    results = col.query(
        query_embeddings=[query_vec],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0], strict=False,
    ):
        output.append({
            "text": doc,
            "law_name": meta.get("law_name", ""),
            "article_no": meta.get("article_no", ""),
            "paragraph_no": meta.get("paragraph_no", ""),
            "article_title": meta.get("article_title", ""),
            "enforcement_date": meta.get("enforcement_date", ""),
            "source_url": meta.get("source_url", ""),
            "score": 1 - dist,  # cosine distance → similarity
        })

    return output


def get_exact_article(law_name: str, article_no: str) -> list[dict]:
    """법령명 + 조번호로 정확 조문 조회."""
    col = _get_collection()
    results = col.get(
        where={"$and": [{"law_name": {"$eq": law_name}}, {"article_no": {"$eq": article_no}}]},
        include=["documents", "metadatas"],
    )
    output = []
    for doc, meta in zip(results["documents"], results["metadatas"], strict=False):
        output.append({"text": doc, **meta})
    return output
