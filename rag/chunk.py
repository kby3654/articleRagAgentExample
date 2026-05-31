"""조문 청크 크기 제어: 너무 길면 분할, 너무 짧으면 인접 항과 병합."""

from __future__ import annotations

from rag.parse import Article

MAX_CHARS = 800
MIN_CHARS = 100


def enforce_chunk_size(articles: list[Article]) -> list[Article]:
    """MAX_CHARS 초과 → 분할 / MIN_CHARS 미만 → 이전 청크에 병합."""
    result: list[Article] = []

    for art in articles:
        if len(art.text) <= MAX_CHARS:
            if (
                result
                and len(result[-1].text) < MIN_CHARS
                and result[-1].law_id == art.law_id
                and result[-1].article_no == art.article_no  # 조 경계 안 넘게
            ):
                # 같은 조 안에서 이전 항이 너무 짧으면 병합 (메타데이터 오염 방지)
                prev = result[-1]
                merged_text = prev.text + "\n" + art.text
                result[-1] = Article(
                    law_name=prev.law_name,
                    law_id=prev.law_id,
                    article_no=prev.article_no,
                    paragraph_no=prev.paragraph_no,
                    item_no=prev.item_no,
                    article_title=prev.article_title,
                    text=merged_text,
                    enforcement_date=prev.enforcement_date,
                    source_url=prev.source_url,
                )
            else:
                result.append(art)
        else:
            # 긴 텍스트는 MAX_CHARS 기준으로 분할
            parts = _split_text(art.text, MAX_CHARS)
            for i, part in enumerate(parts):
                sub = Article(
                    law_name=art.law_name,
                    law_id=art.law_id,
                    article_no=art.article_no,
                    paragraph_no=f"{art.paragraph_no}-{i}" if art.paragraph_no else str(i),
                    item_no=art.item_no,
                    article_title=art.article_title,
                    text=part,
                    enforcement_date=art.enforcement_date,
                    source_url=art.source_url,
                )
                result.append(sub)

    return result


def _split_text(text: str, max_len: int) -> list[str]:
    lines = text.split("\n")
    chunks, buf = [], []
    cur_len = 0
    for line in lines:
        if cur_len + len(line) > max_len and buf:
            chunks.append("\n".join(buf))
            buf, cur_len = [], 0
        buf.append(line)
        cur_len += len(line)
    if buf:
        chunks.append("\n".join(buf))
    return chunks
