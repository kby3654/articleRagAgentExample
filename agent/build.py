"""에이전트 생성 — DeepSeek LLM(OpenAI-compatible) + LangGraph ReAct."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agent.prompts import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS


def _make_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0,
        max_retries=5,
    )


def build_agent():
    """ReAct 에이전트 반환. Google Gemini API 사용 (무료 티어)."""
    agent = create_react_agent(
        model=_make_llm(),
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def build_plain_llm():
    """RAG 없이 순수 LLM. 검색·도구·근거 정책 없음 — 비교용."""
    return _make_llm()
