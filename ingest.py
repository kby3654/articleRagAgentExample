"""법령 수집 → 청킹 → 임베딩 → Chroma 적재 (배치 스크립트).

사용법:
    # 법령명으로 검색해서 자동 인제스트 (권장)
    uv run python ingest.py --query 소방기본법

    # MST(법령일련번호) 직접 지정
    uv run python ingest.py --mst 270329 --law-name 소방기본법 --enforcement-date 20260402

국가법령정보센터 OPEN API:
    https://www.law.go.kr/LSW/openApi.do
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from rag.chunk import enforce_chunk_size
from rag.parse import parse_law_xml
from rag.store import upsert_articles

load_dotenv()

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

LAW_API_BASE = os.getenv("LAW_API_BASE_URL", "https://www.law.go.kr/DRF")
LAW_API_KEY = os.getenv("LAW_API_KEY", "")


def search_law(query: str) -> dict:
    """법령명으로 검색 → 첫 결과의 메타(law_id, mst, name, enforcement_date) 반환."""
    url = f"{LAW_API_BASE}/lawSearch.do"
    params = {"OC": LAW_API_KEY, "target": "law", "type": "JSON", "query": query}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json()["LawSearch"]["law"]
    if not isinstance(items, list):
        items = [items]
    # 정확 법령명 매칭 우선, 없으면 첫 결과
    it = next((x for x in items if x["법령명한글"].strip() == query.strip()), items[0])
    return {
        "law_id": it["법령ID"],
        "mst": it["법령일련번호"],
        "law_name": it["법령명한글"].strip(),
        "enforcement_date": it["시행일자"],
    }


def fetch_law_xml(mst: str) -> str:
    """법령 본문 XML 다운로드 (MST 기준). 로컬 캐시 우선."""
    cache_path = RAW_DIR / f"{mst}.xml"
    if cache_path.exists():
        print(f"[cache] {cache_path}")
        return cache_path.read_text(encoding="utf-8")

    url = f"{LAW_API_BASE}/lawService.do"
    params = {"OC": LAW_API_KEY, "target": "law", "type": "XML", "MST": mst}
    print(f"[fetch] {url} MST={mst}")
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    xml_text = resp.text
    cache_path.write_text(xml_text, encoding="utf-8")
    return xml_text


def ingest_law(mst: str, law_id: str, law_name: str, enforcement_date: str = "") -> int:
    source_url = f"https://www.law.go.kr/법령/{law_name}"

    xml_text = fetch_law_xml(mst)
    articles = parse_law_xml(
        xml_text=xml_text,
        law_id=law_id,
        law_name=law_name,
        enforcement_date=enforcement_date,
        source_url=source_url,
    )
    print(f"[parse] {len(articles)} articles from {law_name}")

    chunks = enforce_chunk_size(articles)
    print(f"[chunk] {len(chunks)} chunks after size enforcement")

    count = upsert_articles(chunks)
    print(f"[upsert] {count} chunks → Chroma")
    return count


def fetch_and_ingest(query: str) -> dict:
    """법령명/키워드로 OPEN API 검색 → 본문 적재 (온디맨드).

    반환: {law_name, mst, enforcement_date, chunks} 또는 {error}.
    """
    if not LAW_API_KEY:
        return {"error": "LAW_API_KEY 미설정"}
    try:
        meta = search_law(query)
    except (KeyError, IndexError, httpx.HTTPError):
        return {"error": f"'{query}' 검색 결과 없음"}

    count = ingest_law(
        mst=meta["mst"],
        law_id=meta["law_id"],
        law_name=meta["law_name"],
        enforcement_date=meta["enforcement_date"],
    )
    return {
        "law_name": meta["law_name"],
        "mst": meta["mst"],
        "enforcement_date": meta["enforcement_date"],
        "chunks": count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="법령 인제스트")
    parser.add_argument("--query", help="법령명 검색어 (예: 소방기본법)")
    parser.add_argument("--mst", help="법령일련번호 직접 지정")
    parser.add_argument("--law-id", default="", help="법령ID (수동 지정 시)")
    parser.add_argument("--law-name", default="", help="법령명 (수동 지정 시)")
    parser.add_argument("--enforcement-date", default="", help="시행일 (예: 20260402)")
    args = parser.parse_args()

    if args.query:
        meta = search_law(args.query)
        print(f"[search] {meta}")
        ingest_law(
            mst=meta["mst"],
            law_id=meta["law_id"],
            law_name=meta["law_name"],
            enforcement_date=meta["enforcement_date"],
        )
    elif args.mst:
        ingest_law(
            mst=args.mst,
            law_id=args.law_id,
            law_name=args.law_name,
            enforcement_date=args.enforcement_date,
        )
    else:
        parser.error("--query 또는 --mst 중 하나는 필수입니다.")

    print("[done]")


if __name__ == "__main__":
    main()
