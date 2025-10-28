# WanteDash AI Assistant

WanteDash는 Discord 봇 인터페이스를 기반으로 하는 다기능 AI 비서 프로젝트입니다. 이 시스템은 고급 RAG(Retrieval-Augmented Generation) 파이프라인, 지능형 쿼리 라우팅, 비용 절감을 위한 의미 체계 캐싱(Semantic Caching), 그리고 관리자를 위한 Streamlit 대시보드를 통합하여 구성되어 있습니다.

## 🌟 핵심 기능

  * **Discord 봇 인터페이스:** 사용자는 Discord의 DM(개인 메시지) 또는 채널 멘션을 통해 봇과 상호작용합니다. (`discord_bot.py`)
  * **고급 RAG 코어 (LangGraph):** LangGraph를 사용하여 복잡한 RAG 및 라우팅 로직을 상태 머신(State Machine)으로 구현합니다. (`rag_core.py`)
  * **지능형 쿼리 라우팅:** 사용자의 질문 의도를 'RAG (규정 질문)', 'Counseling (진로 상담)', 'Chit-chat (일상 대화)'의 3가지로 자동 분류하여 최적의 도구로 처리합니다. (`tools.py`)
  * **선제적 의미 체계 캐시:** 사용자가 '유용했다'고 평가한(satisfaction=1) 로그를 LLM이 검증하여 고품질 Q\&A 쌍을 별도의 캐시 벡터 DB에 저장합니다. 이후 동일/유사 질문은 LLM 호출 없이 0 토큰 비용으로 즉시 응답합니다. (`build_cache.py`, `rag_core.py`)
  * **멀티미디어 데이터 수집:** PDF에서 텍스트뿐만 아니라 이미지와 표(Table)까지 추출하여 RAG의 검색 대상에 포함시킵니다. (`ingest_vectorize.py`)
  * **Streamlit 관리자 대시보드:** 관리자가 채팅 로그 통계(일별 추이, 라우팅 비율)를 시각적으로 확인하고, 새로운 지식 파일(PDF/CSV)을 직접 업로드하여 봇의 지식을 업데이트할 수 있습니다. (`streamlit_app.py`)
  * **자동 리포팅 에이전트:** Streamlit 대시보드에서 버튼 클릭 한 번으로 'Organization AI Agent'(`organization_agent.py`)를 실행, 최근 로그를 분석하여 트렌드 리포트(.md)를 자동으로 생성합니다.
  * **인터랙티브 피드백:** 봇은 답변 후 '만족도 조사' 버튼을 전송하며, RAG 답변 시 '관련 이미지/표 보기' 버튼을 제공하여 사용자가 원본 자료를 요청할 수 있게 합니다.

## 🛠️ 프로젝트 아키텍처

이 프로젝트는 크게 4개의 파이프라인으로 구성됩니다.

### 1\. 사용자 쿼리 흐름 (Discord 봇)

1.  **질문 수신:** 사용자가 Discord에서 봇을 멘션하거나 DM을 보냅니다. (`discord_bot.py`)
2.  **그래프 시작:** `rag_core.py`에 정의된 LangGraph가 실행됩니다.
3.  **[1단계] 캐시 확인:** `cache_check_node`가 `vectorstore/chromadb_cache` (의미 체계 캐시)를 먼저 조회합니다.
      * **Cache Hit (유사도 95% 이상):** LLM 호출 없이 캐시된 답변을 즉시 반환합니다. (비용 0)
      * **Cache Miss:** 다음 단계로 진행합니다.
4.  **[2단계] 라우팅:** `router_question` 노드(LLM 호출)가 질문을 'rag', 'counseling', 'chit\_chat' 중 하나로 분류합니다.
5.  **[3단계] 작업 수행:**
      * **`rag_node`:** (필요시) 질문을 재구성하고 `vectorstore/chromadb_rag` (메인 DB)에서 문서를 검색한 뒤, LLM을 호출하여 답변을 생성합니다.
      * **`counseling_node`:** Tavily Search(웹 검색) 도구를 사용하여 실시간 정보(예: 취업 동향)를 검색하고 LLM이 조언을 생성합니다.
      * **`chit_chat_node`:** LLM이 일상 대화 답변을 생성합니다.
6.  **[4단계] 로깅:** 질문, 답변, 라우팅 경로, (RAG의 경우) 검색된 문맥이 `chat_logs.db` (SQLite)에 저장됩니다.
7.  **[5단계] 피드백:** 봇이 Discord에 답변 및 `SatisfactionView` (만족도) 버튼을 전송합니다.

### 2\. 지식 파이프라인 (데이터 수집)

1.  **초기 수집:** 관리자가 `ingest_vectorize.py`를 실행합니다.
2.  스크립트가 `source_documents` 폴더의 PDF를 `fitz`(PyMuPDF)로 열어 텍스트, 이미지, 표를 추출합니다.
3.  추출된 데이터를 `OpenAIEmbeddings`로 벡터화하여 `vectorstore/chromadb_rag` (메인 벡터 DB)에 저장합니다.
4.  **지식 업데이트:** 관리자가 `streamlit_app.py` 대시보드에 새 PDF/CSV 파일을 업로드하면 동일한 수집 로직이 실행되어 `chromadb_rag`에 데이터가 **추가**됩니다.

### 3\. 의미 체계 캐시 파이프라인 (비용 최적화)

1.  관리자(또는 Cron-job)가 `build_cache.py` 스크립트를 실행합니다.
2.  `chat_logs.db`에서 `satisfaction = 1` (유용함)이고 `processed_for_cache = 0` (미처리)인 로그를 모두 조회합니다.
3.  `organization_tools.py`의 `refine_qa_for_cache` (LLM 호출)를 사용해 각 Q\&A 쌍이 캐시할 가치가 있는지(단순 인사, 농담, 불완전한 답변이 아닌지) 검증합니다.
4.  검증을 통과('APPROVE')한 Q\&A 쌍만 `vectorstore/chromadb_cache` (캐시 벡터 DB)에 저장하고, 처리된 로그는 `processed_for_cache = 1`로 업데이트합니다.

### 4\. 분석 및 리포팅 파이프라인 (관리자)

1.  `streamlit_app.py`가 `chat_logs.db`를 실시간으로 읽어 대시보드에 차트(일별 추이, 유형별 비중)를 표시합니다.
2.  관리자가 대시보드에서 '주간 리포트 생성' 버튼을 클릭합니다.
3.  `organization_agent.py`가 실행되어 `organization_tools.py`의 도구(log 검색, log 분석, 파일 저장)를 순차적으로 호출하며, 최종적으로 `reports/` 폴더에 `.md` 형식의 트렌드 분석 리포트를 저장합니다.

## 📂 파일 구조

```
.
├── source_documents/
│   └── FAQ.pdf             # (예시) RAG의 원본 지식 문서
├── vectorstore/
│   ├── chromadb_rag/       # [DB 1] RAG용 메인 벡터 DB
│   └── chromadb_cache/     # [DB 2] Semantic Cache용 벡터 DB
├── reports/
│   └── 2025-10-28_weekly_report.md # (예시) 조직 에이전트가 생성한 리포트
├── .env                    # API 키 및 토큰 저장
├── discord_bot.py          # [실행 1] 메인 Discord 봇 클라이언트
├── streamlit_app.py        # [실행 2] 관리자용 Streamlit 대시보드
├── ingest_vectorize.py     # [실행 3] (최초 1회) PDF/CSV를 벡터 DB로 수집
├── build_cache.py          # [실행 4] (주기적) 채팅 로그로 Semantic Cache 구축
├── rag_core.py             # RAG 핵심 로직 (LangGraph, DB 설정, 로깅)
├── tools.py                # RAG Core가 사용하는 체인 (라우터, 리라이터, 상담 등)
├── organization_agent.py   # 리포트 생성용 LangGraph 에이전트
├── organization_tools.py   # 리포트 에이전트용 도구 (로그 분석, 캐시 정제 등)
├── chat_logs.db            # [DB 3] 모든 채팅 기록 (SQLite)
└── conversations.db        # [DB 4] LangGraph의 대화 메모리 (SQLite)
```

## 🚀 설치 및 실행

### 1\. 환경 설정

1.  프로젝트를 로컬에 복제(Clone)합니다.
2.  가상 환경을 생성하고 활성화합니다.
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```
3.  필요한 라이브러리를 설치합니다. (주요 라이브러리 목록)
    ```bash
    pip install discord.py python-dotenv langgraph langchain-openai langchain-chroma \
                langchain-community langchain-tavily streamlit plotly pandas \
                PyMuPDF langchain-classic
    ```
4.  `.env` 파일을 생성하고 아래와 같이 API 키를 입력합니다.
    ```env
    OPENAI_API_KEY="sk-..."
    DISCORD_TOKEN="YOUR_DISCORD_BOT_TOKEN"
    TAVILY_API_KEY="tvly-..."
    ```

### 2\. 초기 데이터 수집

봇을 실행하기 전, RAG가 참조할 지식 벡터 DB를 생성해야 합니다.

1.  `source_documents` 폴더에 지식 기반으로 사용할 PDF 파일을 넣습니다. (예: `FAQ.pdf`)
2.  아래 명령어를 실행하여 `vectorstore/chromadb_rag`를 생성합니다.
    ```bash
    python ingest_vectorize.py
    ```

### 3\. 애플리케이션 실행

아래 두 애플리케이션은 동시에 실행되어야 합니다. (터미널 2개 사용)

**A. Discord 봇 실행**

사용자의 질문에 응답하는 봇을 활성화합니다.

```bash
python discord_bot.py
```

**B. 관리자 대시보드 실행**

통계를 확인하고 지식을 업데이트하는 웹 앱을 실행합니다.

```bash
streamlit run streamlit_app.py
```

### 4\. (선택) Semantic Cache 구축

봇이 어느 정도 운영되어 `chat_logs.db`에 `satisfaction = 1`인 로그가 쌓였을 때, 아래 스크립트를 실행하여 캐시 DB를 구축합니다.

```bash
python build_cache.py
```