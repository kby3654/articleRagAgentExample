"""인용 조문 추출 + 실재 여부 검증 (환각률 측정용).

답변 텍스트에서 「OO법 제N조」 형태 인용을 뽑고,
국가법령정보센터 OPEN API로 해당 법령의 실제 조문 집합과 대조한다.
순수 LLM이 존재하지 않는 조문을 인용하면 여기서 잡힌다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import fetch_law_xml, search_law  # noqa: E402
from rag.parse import parse_law_xml  # noqa: E402

# 「소방기본법」 제25조 / 소방기본법 제25조 제1항 / (소방기본법 제25조) 등 매칭
# 법령명 = 한글·숫자·중점(·ㆍ)·괄호 조합, '법' 또는 '률' 또는 '규칙'으로 끝남
_CITATION_RE = re.compile(
    r"[「(\(]?\s*"
    r"([가-힣A-Za-z0-9·ㆍ\s]+?(?:법률|특별법|법|률|규칙))"
    r"[」)\)]?\s*"
    r"제\s*(\d+)\s*조"
)

# 법령명 → 실제 조문번호 집합 캐시
_article_cache: dict[str, set[str]] = {}


def extract_citations(text: str) -> list[tuple[str, str]]:
    """답변에서 (법령명, 조번호) 튜플 리스트 추출 (중복 제거, 등장순)."""
    out: list[tuple[str, str]] = []
    seen = set()
    for m in _CITATION_RE.finditer(text):
        law = _normalize_law_name(m.group(1))
        jo = m.group(2)
        key = (law, jo)
        if law and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _normalize_law_name(name: str) -> str:
    # 내부 공백은 보존(이태원 특별법 등 띄어쓰기 법령명), 양끝/중복만 정리
    return re.sub(r"\s+", " ", name).strip()


def _resolve_article_set(name: str) -> set[str] | None:
    meta = search_law(name)
    xml_text = fetch_law_xml(meta["mst"])
    articles = parse_law_xml(
        xml_text=xml_text,
        law_id=meta["law_id"],
        law_name=meta["law_name"],
        enforcement_date=meta["enforcement_date"],
        source_url="",
    )
    return {a.article_no for a in articles if a.article_no}


def get_article_set(law_name: str) -> set[str] | None:
    """법령의 실제 조문번호 집합 반환. 검색 실패 시 None.

    인용 추출에서 앞 단어가 붙는 경우 대비: 공백 기준 앞 토큰을 하나씩
    떼며 재시도 (예: '가짜로 소방기본법' → '소방기본법').
    """
    if law_name in _article_cache:
        return _article_cache[law_name]

    candidates = [law_name]
    tokens = law_name.split(" ")
    for i in range(1, len(tokens)):
        candidates.append(" ".join(tokens[i:]))

    for cand in candidates:
        try:
            nos = _resolve_article_set(cand)
            if nos:
                _article_cache[law_name] = nos
                return nos
        except Exception:
            continue

    _article_cache[law_name] = None  # type: ignore[assignment]
    return None


def citation_exists(law_name: str, article_no: str) -> bool | None:
    """인용 조문이 실제 존재하는지. None = 법령 자체를 못 찾음(검증 불가)."""
    nos = get_article_set(law_name)
    if nos is None:
        return None
    return article_no in nos
