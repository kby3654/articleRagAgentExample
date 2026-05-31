# 법령 정보 RAG 에이전트

한국 법령 데이터 기반 RAG — 근거 조문을 명시한 답변 제공.

## 스택

| 항목 | 선택 |
|------|------|
| LLM | DeepSeek API (`deepseek-chat`) |
| 임베딩 | OpenAI `text-embedding-3-small` (DeepSeek 호환) |
| 벡터 DB | Chroma (로컬 영속화) |
| 오케스트레이션 | LangGraph `create_react_agent` |
| UI | Streamlit |
| 패키지 관리 | uv / ruff |

## 빠른 시작

### 1. 환경 설정

```bash
cp .env.example .env
# .env 편집: DEEPSEEK_API_KEY, LAW_API_KEY 입력
```

### 2. 의존성 설치

```bash
uv sync
```

### 3. 법령 인제스트 (최초 1회)

```bash
# 소방기본법 예시
uv run python ingest.py --law-id OC0000051 --law-name 소방기본법 --enforcement-date 20240101
```

법령 ID는 [국가법령정보센터 OPEN API](https://www.law.go.kr/LSW/openApi.do)에서 확인.

### 4. 앱 실행

```bash
uv run streamlit run app.py
```

### 5. 평가

```bash
uv run python eval/run_eval.py
```

## 디렉토리 구조

```
law-rag-agent/
├── app.py          # Streamlit UI
├── ingest.py       # 배치 인제스트
├── agent/
│   ├── build.py    # create_react_agent
│   ├── tools.py    # search_statutes, get_article
│   └── prompts.py  # 시스템 프롬프트
├── rag/
│   ├── parse.py    # XML 파싱 → Article
│   ├── chunk.py    # 청크 크기 제어
│   └── store.py    # Chroma upsert/search
├── data/
│   ├── raw/        # API 원본 캐시
│   └── chroma/     # 벡터 인덱스
└── eval/
    ├── questions.yaml
    └── run_eval.py
```

## 면책

본 시스템 응답은 법률 자문이 아닌 정보 제공 목적입니다. 실제 법적 판단은 변호사 등 전문가에게 확인하십시오.
