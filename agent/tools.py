"""에이전트 도구 정의."""

from __future__ import annotations

from langchain_core.tools import tool

from rag.store import get_exact_article, search


@tool
def search_statutes(query: str, law_name: str | None = None, k: int = 5) -> list[dict]:
    """질의와 관련된 법조문을 벡터 검색으로 찾는다.

    Args:
        query: 검색할 자연어 질의
        law_name: 특정 법령으로 한정할 때 법령명 전체 (예: "소방기본법"). None이면 전체 검색.
        k: 반환할 최대 결과 수
    """
    results = search(query=query, k=k, law_name=law_name)
    return [
        {
            "law": r["law_name"],
            "article": r["article_no"],
            "paragraph": r["paragraph_no"],
            "title": r["article_title"],
            "text": r["text"],
            "enforcement_date": r["enforcement_date"],
            "url": r["source_url"],
            "similarity": round(r["score"], 4),
        }
        for r in results
    ]


@tool
def get_article(law_name: str, article_no: str) -> list[dict]:
    """법령명과 조 번호로 정확한 조문 원문을 조회한다.

    Args:
        law_name: 법령명 (예: "소방기본법")
        article_no: 조 번호 숫자 문자열 (예: "25")
    """
    results = get_exact_article(law_name=law_name, article_no=article_no)
    if not results:
        return [{"error": f"{law_name} 제{article_no}조를 찾을 수 없습니다."}]
    return results


@tool
def fetch_law_online(law_name: str) -> dict:
    """적재된 법령에 없을 때 국가법령정보센터 OPEN API에서 법령을 실시간 조회·적재한다.

    search_statutes 결과가 비어있거나 관련 법령이 없을 때 호출한다.
    적재 성공 후 다시 search_statutes로 검색하면 해당 법령 조문이 나온다.

    Args:
        law_name: 조회할 법령명 또는 키워드 (예: "이태원참사 특별법", "도로교통법")
    """
    from ingest import fetch_and_ingest

    return fetch_and_ingest(law_name)


ALL_TOOLS = [search_statutes, get_article, fetch_law_online]
