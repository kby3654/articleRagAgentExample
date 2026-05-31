"""Streamlit 웹 UI — 법령 RAG 에이전트."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

load_dotenv()

st.set_page_config(page_title="법령 안내 에이전트", page_icon="⚖️", layout="wide")

DISCLAIMER = "⚠️ 본 서비스는 법률 자문이 아닌 정보 제공 목적입니다. 실제 법적 판단은 변호사 등 전문가에게 확인하세요."


@st.cache_resource
def get_agent():
    from agent.build import build_agent
    return build_agent()


@st.cache_resource
def get_plain_llm():
    from agent.build import build_plain_llm
    return build_plain_llm()


def _content_to_text(content) -> str:
    """LLM 메시지 content를 문자열로 정규화. Gemini는 list[dict] 반환."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and "text" in p:
                parts.append(p["text"])
        return "".join(parts)
    return str(content)


def extract_citations(text: str) -> list[str]:
    """답변에서 (법령명 제N조...) 패턴 인용 추출."""
    import re
    pattern = r"[\(（]([^)）]+제\d+조[^)）]*)[\)）]"
    return list(dict.fromkeys(re.findall(pattern, text)))


# ── 레이아웃
st.title("⚖️ 법령 안내 에이전트")
st.caption(DISCLAIMER)

with st.sidebar:
    compare_mode = st.toggle("🔬 RAG 없이 비교", value=False,
                             help="동일 질문을 RAG 에이전트와 순수 LLM에 각각 보내 답변을 나란히 비교합니다. (LLM 호출 2배 → 쿼터 2배 소모)")

col_chat, col_refs = st.columns([2, 1])

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "citations" not in st.session_state:
    st.session_state.citations = []
if "plain_by_idx" not in st.session_state:
    st.session_state.plain_by_idx = {}  # assistant 메시지 인덱스 → 순수 LLM 답변


def _render_assistant(idx: int, rag_text: str):
    plain_text = st.session_state.plain_by_idx.get(idx)
    if plain_text is None:
        st.markdown(rag_text)
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("🟢 RAG (근거 기반)")
            st.markdown(rag_text)
        with c2:
            st.caption("⚪ 순수 LLM (검색 없음)")
            st.markdown(plain_text)


# ── 채팅 영역
with col_chat:
    for i, msg in enumerate(st.session_state.messages):
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        else:
            with st.chat_message("assistant"):
                _render_assistant(i, msg.content)

    if prompt := st.chat_input("법령 관련 질문을 입력하세요..."):
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("법령 검색 중..."):
            agent = get_agent()
            result = agent.invoke({"messages": st.session_state.messages})
            full_response = _content_to_text(result["messages"][-1].content)

        plain_response = None
        if compare_mode:
            with st.spinner("순수 LLM 답변 생성 중..."):
                plain_msg = get_plain_llm().invoke(prompt)
                plain_response = _content_to_text(plain_msg.content)

        st.session_state.messages.append(AIMessage(content=full_response))
        assistant_idx = len(st.session_state.messages) - 1
        if plain_response is not None:
            st.session_state.plain_by_idx[assistant_idx] = plain_response
        st.session_state.citations = extract_citations(full_response)
        st.rerun()

# ── 근거 조문 패널
with col_refs:
    st.subheader("📋 인용 조문")
    if st.session_state.citations:
        for cite in st.session_state.citations:
            st.info(cite)
    else:
        st.caption("답변의 인용 조문이 여기에 표시됩니다.")

    st.divider()
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.session_state.citations = []
        st.session_state.plain_by_idx = {}
        st.rerun()

# ── 하단 면책
st.divider()
st.caption(DISCLAIMER)
