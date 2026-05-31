"""RAG vs 순수 LLM 비교 평가 하니스.

지표 4종:
  1. 인용 존재율 (1 - 환각률): 인용한 조문이 실제로 존재하는 비율  [헤드라인]
  2. Retrieval Recall@k: 정답 조문이 검색 top-k에 포함되는 비율   [RAG 진단]
  3. 거부 정확도: no_evidence 질문에 "모름"이라 답한 비율
  4. 근거 정확도: 인용 조문이 정답 라벨과 일치 → manual_review.csv 수동 채점

CLI 실행:
    uv run python eval/run_eval.py
Streamlit:
    pages/평가.py 에서 run_evaluation() 호출
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from agent.build import build_agent, build_plain_llm  # noqa: E402
from eval.lawcheck import citation_exists, extract_citations  # noqa: E402
from rag.store import search  # noqa: E402

K = 5
BUCKETS = ("famous", "minor", "recent", "no_evidence")
REFUSAL_MARKERS = [
    "찾지 못", "찾을 수 없", "관련 법령", "근거를 찾", "모르",
    "확인할 수 없", "규정되어 있지 않", "해당 내용이 없", "존재하지 않",
]


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p["text"] if isinstance(p, dict) and "text" in p else (p if isinstance(p, str) else "")
            for p in content
        )
    return str(content)


def run_rag(agent, query: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return _content_to_text(result["messages"][-1].content)


def run_plain_llm(llm, query: str) -> str:
    return _content_to_text(llm.invoke(query).content)


def is_refusal(text: str) -> bool:
    return any(m in text for m in REFUSAL_MARKERS)


def recall_at_k(expected_laws: list[dict], query: str, k: int) -> float | None:
    if not expected_laws:
        return None
    hits, total = 0, 0
    for spec in expected_laws:
        retrieved = search(query=query, k=k, law_name=spec["law_name"])
        got = {r["article_no"] for r in retrieved}
        for ano in spec["article_nos"]:
            total += 1
            if ano in got:
                hits += 1
    return hits / total if total else None


def _check_cites(answer: str) -> list[dict]:
    """답변 인용 → [{law, article_no, exists}] (exists: True/False/None)."""
    out = []
    for law, jo in extract_citations(answer):
        out.append({"law": law, "article_no": jo, "exists": citation_exists(law, jo)})
    return out


def run_evaluation(progress_cb=None) -> dict:
    """평가 실행. progress_cb(done, total, label) 호출 가능.

    반환:
        {
          "records": [ per-question dict ... ],
          "stats":   stats[system][bucket],
          "review_rows": [...],  # CSV용
          "k": K,
        }
    """
    qpath = Path(__file__).parent / "questions.yaml"
    questions = yaml.safe_load(qpath.read_text(encoding="utf-8"))["questions"]

    agent = build_agent()
    plain = build_plain_llm()

    stats = {
        s: defaultdict(lambda: {
            "cite_total": 0, "cite_exist": 0, "cite_unknown": 0,
            "refusal_ok": 0, "refusal_total": 0,
            "recall_sum": 0.0, "recall_n": 0,
        })
        for s in ("rag", "plain")
    }
    records = []
    review_rows = []
    total = len(questions)

    for idx, q in enumerate(questions):
        qid, bucket, query = q["id"], q["bucket"], q["query"]
        expected = q.get("expected_laws", []) or []

        if progress_cb:
            progress_cb(idx, total, f"[{qid}] {query[:30]}…")

        rec = recall_at_k(expected, query, K)
        if rec is not None:
            stats["rag"][bucket]["recall_sum"] += rec
            stats["rag"][bucket]["recall_n"] += 1

        record = {"id": qid, "bucket": bucket, "query": query,
                  "expected": expected, "recall": rec}

        for system, runner in (
            ("rag", lambda x: run_rag(agent, x)),
            ("plain", lambda x: run_plain_llm(plain, x)),
        ):
            try:
                answer = runner(query)
            except Exception as e:
                record[f"{system}_answer"] = f"[ERROR] {e}"
                record[f"{system}_cites"] = []
                record[f"{system}_refused"] = False
                continue

            cites = _check_cites(answer)
            refused = is_refusal(answer) and not cites
            st = stats[system][bucket]

            if bucket == "no_evidence":
                st["refusal_total"] += 1
                if refused:
                    st["refusal_ok"] += 1

            for c in cites:
                st["cite_total"] += 1
                if c["exists"] is True:
                    st["cite_exist"] += 1
                elif c["exists"] is None:
                    st["cite_unknown"] += 1
                review_rows.append({
                    "id": qid, "bucket": bucket, "system": system, "query": query,
                    "law": c["law"], "article_no": c["article_no"],
                    "exists": {True: "Y", False: "N", None: "?"}[c["exists"]],
                    "relevant": "",
                })

            record[f"{system}_answer"] = answer
            record[f"{system}_cites"] = cites
            record[f"{system}_refused"] = refused

        records.append(record)

    if progress_cb:
        progress_cb(total, total, "완료")

    return {"records": records, "stats": stats, "review_rows": review_rows, "k": K}


def write_review_csv(review_rows: list[dict], path: Path | None = None) -> Path:
    path = path or (Path(__file__).parent / "manual_review.csv")
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "bucket", "system", "query", "law", "article_no", "exists", "relevant"]
        )
        writer.writeheader()
        writer.writerows(review_rows)
    return path


def _print_summary(result: dict) -> None:
    stats, k = result["stats"], result["k"]
    print("\n" + "=" * 72)
    print(f"{'system':6} {'bucket':12} {'존재율':>8} {'Recall@k':>9} {'거부정확도':>10}  {'n_cite':>6}")
    print("-" * 72)
    for system in ("rag", "plain"):
        for bucket in BUCKETS:
            st = stats[system][bucket]
            ct = st["cite_total"]
            exist_rate = f"{st['cite_exist']/ct:.2f}" if ct else "  -"
            rk = f"{st['recall_sum']/st['recall_n']:.2f}" if st["recall_n"] else "  -"
            ref = f"{st['refusal_ok']}/{st['refusal_total']}" if st["refusal_total"] else "  -"
            print(f"{system:6} {bucket:12} {exist_rate:>8} {rk:>9} {ref:>10}  {ct:>6}")
    print("=" * 72)
    print(f"존재율 = 1 - 인용환각률 (높을수록 좋음). Recall@{k}는 RAG 코퍼스 기준.")


def main() -> None:
    result = run_evaluation(
        progress_cb=lambda d, t, label: print(f"[{d}/{t}] {label}")
    )
    _print_summary(result)
    csv_path = write_review_csv(result["review_rows"])
    print(f"\n[manual] {csv_path} — relevant 열(1/0) 채우면 근거 정확도 완성. 총 {len(result['review_rows'])} 인용.")


if __name__ == "__main__":
    main()
