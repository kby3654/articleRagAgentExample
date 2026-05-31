"""법령 OPEN API 응답(XML) → 구조화된 조문 리스트로 파싱."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Article:
    law_name: str
    law_id: str
    article_no: str
    paragraph_no: str
    item_no: str
    article_title: str
    text: str
    enforcement_date: str
    source_url: str
    chunk_id: str = field(init=False)

    def __post_init__(self):
        self.chunk_id = f"{self.law_id}::{self.article_no}::{self.paragraph_no}"


def parse_law_xml(xml_text: str, law_id: str, law_name: str, enforcement_date: str, source_url: str) -> list[Article]:
    """법령 본문 XML → Article 리스트 (조-항 단위 분해)."""
    root = ET.fromstring(xml_text)
    articles: list[Article] = []

    for jo_elem in root.iter("조문단위"):
        # 실제 조문만(가지번호 등 wrapper 제외) — 조문여부 == "조문"
        if jo_elem.findtext("조문여부", "조문").strip() not in ("조문", ""):
            continue

        article_no = jo_elem.findtext("조문번호", "").strip()
        article_title = jo_elem.findtext("조문제목", "").strip()
        jo_text_elem = jo_elem.find("조문내용")
        jo_base_text = jo_text_elem.text.strip() if jo_text_elem is not None and jo_text_elem.text else ""

        hangs = jo_elem.findall("항")
        if not hangs:
            # 항이 없으면 조 전체를 단일 청크
            articles.append(Article(
                law_name=law_name,
                law_id=law_id,
                article_no=article_no,
                paragraph_no="",
                item_no="",
                article_title=article_title,
                text=_build_header(law_name, article_no, article_title) + jo_base_text,
                enforcement_date=enforcement_date,
                source_url=source_url,
            ))
        else:
            for idx, hang_elem in enumerate(hangs):
                para_no = hang_elem.findtext("항번호", "").strip()
                para_text = hang_elem.findtext("항내용", "").strip()
                # 호 = 호번호 + 호내용, 목 = 목번호 + 목내용 까지 병합
                ho_lines = []
                for ho in hang_elem.findall("호"):
                    ho_no = ho.findtext("호번호", "").strip()
                    ho_text = ho.findtext("호내용", "").strip()
                    ho_lines.append(f"  {ho_text}" if ho_text else f"  {ho_no}")
                    for mok in ho.findall("목"):
                        mok_text = mok.findtext("목내용", "").strip()
                        if mok_text:
                            ho_lines.append(f"    {mok_text}")

                full_text = para_text
                if ho_lines:
                    full_text = (full_text + "\n" if full_text else "") + "\n".join(ho_lines)
                if not full_text:
                    continue

                # 항번호 없으면(단일 항) 조 텍스트에 인덱스 부여
                paragraph_no = para_no or (str(idx) if len(hangs) > 1 else "")

                articles.append(Article(
                    law_name=law_name,
                    law_id=law_id,
                    article_no=article_no,
                    paragraph_no=paragraph_no,
                    item_no="",
                    article_title=article_title,
                    text=_build_header(law_name, article_no, article_title) + full_text,
                    enforcement_date=enforcement_date,
                    source_url=source_url,
                ))

    return articles


def _build_header(law_name: str, article_no: str, article_title: str) -> str:
    title_part = f"({article_title})" if article_title else ""
    return f"[{law_name} 제{article_no}조{title_part}]\n"
