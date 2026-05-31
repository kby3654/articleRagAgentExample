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
# .env 편집: API_KEY, LAW_API_KEY 입력
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

Gemini Flash 사용한 샘플
<img width="1794" height="875" alt="스크린샷 2026-05-31 164056" src="https://github.com/user-attachments/assets/6a75e9f1-c6d8-466e-9c99-a1b3703804c7" />
<img width="1389" height="820" alt="스크린샷 2026-05-31 164412" src="https://github.com/user-attachments/assets/fe666332-6463-4af9-b386-4b5778352356" />


DeepSeek 모델 사용한 샘플

<img width="1590" height="823" alt="스크린샷 2026-05-31 215627" src="https://github.com/user-attachments/assets/900125d2-2d48-46cf-be1d-e8cba132ffe4" />


<img width="1556" height="792" alt="스크린샷 2026-05-31 203330" src="https://github.com/user-attachments/assets/a3384427-337c-4800-995e-0f55a7ca23c0" />
<img width="1572" height="861" alt="스크린샷 2026-05-31 203348" src="https://github.com/user-attachments/assets/5f7d9864-264b-4fb5-a92f-dd8242da6680" />
<img width="1562" height="800" alt="스크린샷 2026-05-31 203554" src="https://github.com/user-attachments/assets/1d822fa2-ab80-4266-a8ce-155baaadb365" />
<img width="1611" height="849" alt="스크린샷 2026-05-31 203417" src="https://github.com/user-attachments/assets/7a3912f8-6a5b-49cb-818c-325816c66670" />
<img width="1560" height="853" alt="스크린샷 2026-05-31 203641" src="https://github.com/user-attachments/assets/e4228136-53c2-4c47-9d10-804c39be0774" />

