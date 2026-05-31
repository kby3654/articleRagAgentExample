"""Streamlit 평가 페이지 — RAG vs 순수 LLM 비교 결과를 화면에서 본다."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from eval.run_eval import BUCKETS, run_evaluation, write_review_csv  # noqa: E402

st.set_page_config(page_title="평가 · RAG vs 순수 LLM", page_icon="📊", layout="wide")

st.title("📊 RAG vs 순수 LLM 비교 평가")
st.caption("정답 라벨 평가셋으로 인용 존재율(=1−환각률)·Recall@k·거부 정확도를 측정합니다.")

st.info(
    "⏱️ 24문항 × 2시스템 ≈ 48회 LLM 호출 + 인용 검증 API 호출. 수 분 소요. "
    "Gemini 쿼터를 소모합니다.",
    icon="⚠️",
)


def _summary_df(stats: dict, k: int) -> pd.DataFrame:
    rows = []
    for system in ("rag", "plain"):
        for bucket in BUCKETS:
            s = stats[system][bucket]
            ct = s["cite_total"]
            rows.append({
                "시스템": "🟢 RAG" if system == "rag" else "⚪ 순수 LLM",
                "버킷": bucket,
                "존재율(1−환각)": round(s["cite_exist"] / ct, 2) if ct else None,
                f"Recall@{k}": round(s["recall_sum"] / s["recall_n"], 2) if s["recall_n"] else None,
                "거부정확도": f"{s['refusal_ok']}/{s['refusal_total']}" if s["refusal_total"] else "—",
                "인용수": ct,
            })
    return pd.DataFrame(rows)


def _cites_md(cites: list[dict]) -> str:
    if not cites:
        return "_(인용 없음)_"
    mark = {True: "✅", False: "❌실재X", None: "❔검증불가"}
    return "\n".join(f"- {c['law']} 제{c['article_no']}조 {mark[c['exists']]}" for c in cites)


if st.button("▶️ 평가 실행", type="primary"):
    bar = st.progress(0.0, text="시작…")

    def cb(done, total, label):
        bar.progress(done / total, text=f"{done}/{total} · {label}")

    with st.spinner("평가 중… (수 분 소요)"):
        result = run_evaluation(progress_cb=cb)

    st.session_state.eval_result = result
    csv_path = write_review_csv(result["review_rows"])
    st.session_state.eval_csv = str(csv_path)
    bar.empty()
    st.success("평가 완료")

# ── 결과 표시
result = st.session_state.get("eval_result")
if result:
    st.subheader("요약 — 시스템 × 버킷")
    df = _summary_df(result["stats"], result["k"])
    rag_df = df[df["시스템"] == "🟢 RAG"].reset_index(drop=True)
    plain_df = df[df["시스템"] == "⚪ 순수 LLM"].reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 헤드라인: 버킷별 존재율 대비
    st.subheader("헤드라인 — 버킷별 인용 존재율 (높을수록 환각 적음)")
    pivot = df.pivot_table(index="버킷", columns="시스템", values="존재율(1−환각)").reindex(BUCKETS)
    st.bar_chart(pivot)

    csv_path = st.session_state.get("eval_csv")
    if csv_path and Path(csv_path).exists():
        st.download_button(
            "⬇️ manual_review.csv 내려받기 (relevant 열 채워 근거 정확도 완성)",
            data=Path(csv_path).read_bytes(),
            file_name="manual_review.csv",
            mime="text/csv",
        )

    st.subheader("문항별 답변 비교")
    bucket_filter = st.multiselect("버킷 필터", BUCKETS, default=list(BUCKETS))
    for rec in result["records"]:
        if rec["bucket"] not in bucket_filter:
            continue
        rectag = f"`{rec['bucket']}`"
        rec_str = f" · Recall@{result['k']}={rec['recall']:.2f}" if rec["recall"] is not None else ""
        with st.expander(f"[{rec['id']}] {rectag} {rec['query']}{rec_str}"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🟢 RAG**")
                if rec.get("rag_refused"):
                    st.warning("거부(모름)")
                st.markdown(_cites_md(rec.get("rag_cites", [])))
                st.markdown("---")
                st.markdown(rec.get("rag_answer", "_(없음)_"))
            with c2:
                st.markdown("**⚪ 순수 LLM**")
                if rec.get("plain_refused"):
                    st.warning("거부(모름)")
                st.markdown(_cites_md(rec.get("plain_cites", [])))
                st.markdown("---")
                st.markdown(rec.get("plain_answer", "_(없음)_"))
else:
    st.caption("▶️ 평가 실행 버튼을 눌러 시작하세요.")
