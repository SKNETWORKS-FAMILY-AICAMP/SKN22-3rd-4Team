# 📊 미국 재무제표 분석 및 투자 인사이트 봇

> AI 기반 미국 상장사 재무제표 분석 및 투자 조언 플랫폼

## 🎯 프로젝트 목표

미국 상장 기업의 방대한 재무 데이터와 시장 정보를 AI로 분석하여, 투자자에게 실질적인 인사이트를 제공하는 대화형 플랫폼을 구축합니다.

## 🙋‍♂️ 프로젝트 팀 구성 (Team Composition)

| Role & Name | Responsibilities | Comment |
| :--- | :--- | :--- |
| **이병재 (Team Leader)**<br><sub>PM / ARCHITECTURE / DB</sub><br>[@PracLee](https://github.com/PracLee) | • 프로젝트 기획 및 전체 구조(Architecture) 설계<br>• 재무 데이터베이스(DB) 모델링 및 설계<br>• 챗봇 추천 검색어 로직 구현<br>• 단위/통합 테스트 주도 및 품질 관리 | 단순히 프롬프트만 고치는 게 아니라 로직 밑바닥까지 직접 디버깅하며 RAG 성능을 50% 넘게 끌어올렸을 때, 진짜 엔지니어링의 재미를 느꼈습니다. |
| **장완식 (Core Dev)**<br><sub>RAG PIPELINE / UI/UX</sub><br>[@JangWS1030](https://github.com/JangWS1030) | • RAG 파이프라인(Chatbot) 핵심 로직 구현<br>• 로그인/인증 시스템 및 즐겨찾기 기능 개발<br>• DB 현황 모니터링 UI 및 PDF 리포트 수정<br>• 전반적인 UI/UX 개선 및 고도화 | AI는 마법이 아니라 공학임을 깨닫고, 데이터 기반의 집요한 검증과 디버깅으로 성능 한계를 극복하며 엔지니어링의 본질을 체득했습니다 |
| **안민제 (Feature Dev)**<br><sub>SEARCH / QA / DOCS / DB</sub><br>[@minje0209-ux](https://github.com/minje0209-ux) | • 챗봇 검색어 자동완성 알고리즘 구현<br>• 추천 검색어 기능 고도화<br>• ticker/keyword DB 설계<br>• 챗봇/리포트 작성 프롬프트 고도화<br>• README.md 작성 및 기술 문서화 | 스트림릿에 꽤 좋은 도구가 많더라구요! 재밌었어요. |
| **이신재 (Frontend / QA)**<br><sub>TESTING / UI REFINEMENT</sub><br>[@Codingcooker74](https://github.com/Codingcooker74) | • 주요 기능 단위 테스트(Unit Test) 수행<br>• 사용자 인터페이스(UI) 오류 수정 및 폴리싱<br>• 반응형 레이아웃 최적화 지원 | 어려운 것을 척척해네는 팀원들이 대단해 보였습니다.^^ |

## 🖐️ 핵심 기능

1. **💬 AI Financial Analyst**: Finnhub 실시간 데이터와 내부 재무 DB를 결합한 RAG 챗봇 (병렬 수집 최적화로 빠른 응답)
2. **📝 투자 리포트 + 주가 차트**: 단일/비교 분석 레포트 생성 + 3개월 주가 추이 차트 (`gpt-4.1-mini`, 한글명 검색)
3. **📈 한국형 마켓 대시보드**: KST 기준 실시간 원화(KRW) 환율 및 주요 지표 제공
4. **⭐ 사이드바 관심기업 Quick Add**: 어디서든 티커/한글명으로 즐겨찾기 추가 (DB 검증)
5. **🔍 Text-to-SQL**: 자연어 질의를 통한 복잡한 재무 재표 검색

---

## 🏗️ 시스템 아키텍처

```mermaid
graph TD
    User([👤 사용자]) -->|1. 접속| Login[🔐 로그인/회원가입]
    Login -->|2. 인증 성공| UI[💻 Streamlit Web App]
    
    subgraph Frontend Logic
        Login -->|Auth Request| Auth[🔐 Supabase Auth]
        UI -->|Chat Query| Validator[🛡️ Input Validator]
        UI -->|Report Request| ReportGen[📝 Report Generator]
        UI -->|Manage Favorites| Watchlistmgr[⭐ Watchlist Manager]
    end

    subgraph Data & State
        Auth <-->|Verify| UserDB[(👥 Users Table)]
        Watchlistmgr <-->|Sync| UserDB
    end

    subgraph RAG Engine
        Validator -->|Valid Query| Agent[🤖 LangChain Agent]
        ReportGen -->|Data Fetch| Retriever[🔍 Data Retriever]
        
        Agent <-->|Vector Search| VectorDB[(🗄️ Supabase Vector)]
        Agent <-->|Graph Search| GraphDB[(🕸️ GraphRAG)]
        
        Retriever -->|Parallel Fetch| VectorDB
        Retriever -->|Parallel Fetch| GraphDB
    end

    subgraph Data Sources
        Retriever -->|Live Price/News| Finnhub[📡 Finnhub API]
        Retriever -->|Market Info| Yahoo[📈 yfinance API]
        Retriever -->|Unknown Ticker| Tavily[🕵️ Tavily Search]
        VectorDB <-->|Sync| SEC[📄 SEC 10-K]
    end

    Retriever -->|Aggregated Context| LLM[🧠 GPT-4.1-mini]
    Agent -->|Final Answer| LLM
    LLM -->|Response| UI
```

---

## 🕸️ GraphRAG: 지능형 관계망 분석

단순한 텍스트 검색(Vector RAG)을 넘어, 기업 간의 **공급망(Supply Chain), 경쟁 구도, 지배 구조**를 연결하여 입체적인 분석을 제공합니다.

### 1. GraphRAG 작동 원리 (Architecture)

```mermaid
graph TD
    subgraph "1. 데이터 추출 (Ingestion)"
        A[Original Text / 10-K] --> B{LLM 관계 추출}
        B -- "추출" --> C(JSON: Source-Target-Relationship)
        C -- "저장" --> D[(Supabase: company_relationships)]
    end

    subgraph "2. 네트워크 구축 (Graph Building)"
        D --> E[NetworkX 로컬 그래프 생성]
        E --> F[Nodes: 기업/브랜드]
        E --> G[Edges: 파트너, 경쟁사, 자회사 등]
    end

    subgraph "3. 지능형 검색 (Query)"
        H[사용자 질문: '애플의 공급망 분석'] --> I{그래프 탐색}
        I --> J[1/2단계 인접 노드 탐색]
        J --> K[중심성 분석 / 최단 경로 계산]
        K --> L[그래프 컨텍스트 생성]
    end

    subgraph "4. 인사이트 생성"
        L --> M{Analyst LLM}
        M --> N[입체적 투자 인사이트 답변]
    end
```

### 2. 주요 기능

- **관계망 추론**: 특정 기업의 악재가 공급망 내 어떤 기업에 파급될지 분석합니다.
- **네트워크 위치 분석**: NetworkX의 `Centrality(중심성)` 알고리즘을 사용하여 시장 내 핵심 기업을 식별합니다.
- **다차원 컨텍스트**: 벡터 검색 결과와 그래프 분석 결과를 결합하여 정보의 누락 없는 답변을 생성합니다.

---

## 🛡️ 보안 및 안전성 (Security & Reliability)

사용자 정보 보호와 시스템 무결성을 위해 **3단계 보안 레이어**를 구축하였습니다.

- **Layer 1 (Gateway)**: 요청 속도 제한(Rate Limit) 및 반복 공격 세션 자동 차단.
- **Layer 2 (Validator)**: 코드 레벨의 프롬프트 인젝션 패턴 탐지 및 입력 정제.
- **Layer 3 (Guard)**: 시스템 프롬프트 하드닝(Hardening)을 통한 페르소나 이탈 방지.

> [상세 보안 가이드 확인하기](./docs/SECURITY_SYSTEM.md)

---

## 📚 기술 스택

![Python](https://img.shields.io/badge/Python-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-%23FF4B4B.svg?style=for-the-badge&logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-%23412991.svg?style=for-the-badge&logo=openai&logoColor=white)
![GraphRAG](https://img.shields.io/badge/GraphRAG-%23000000.svg?style=for-the-badge&logo=graphrag&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-%233ECF8E.svg?style=for-the-badge&logo=supabase&logoColor=white)
![Finnhub](https://img.shields.io/badge/Finnhub-%2300C7B7.svg?style=for-the-badge&logo=finnhub&logoColor=white)
![yfinance](https://img.shields.io/badge/yfinance-%23F7CA18.svg?style=for-the-badge&logo=finance&logoColor=black)
![NetworkX](https://img.shields.io/badge/NetworkX-%23F9A825.svg?style=for-the-badge&logo=networkx&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-%233F4F75.svg?style=for-the-badge&logo=plotly&logoColor=white)
![ReportLab](https://img.shields.io/badge/ReportLab-%23555555.svg?style=for-the-badge&logo=reportlab&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-%238A2BE2.svg?style=for-the-badge&logo=apscheduler&logoColor=white)
![lxml](https://img.shields.io/badge/lxml-%23CCCCCC.svg?style=for-the-badge&logo=lxml&logoColor=black)
![Tavily](https://img.shields.io/badge/Tavily-%23007BFF.svg?style=for-the-badge&logo=tavily&logoColor=white)

---

## 📸 주요 기능 및 실행 화면

### 1. 📊 메인 대시보드 (Home)

KST 기준 실시간 환율 정보와 관심 기업(Watchlist)을 한눈에 확인할 수 있습니다.
![Main Dashboard](./docs/images/dashboard_preview.png)

### 2. 💬 AI 애널리스트 채팅 (RAG Chatbot)

재무제표 DB와 실시간 뉴스 데이터를 기반으로 사용자의 투자 질문에 답변합니다. (출처 포함)
![Chat Interface](./docs/images/chat_preview.png)

### 3. 📝 심층 투자 리포트 (Report Generator)

단일 기업 분석부터 다중 기업 비교까지, 전문가 수준의 PDF 리포트를 원클릭으로 생성합니다.

**특징**: 주가 차트, 거래량, 재무 지표 시각화 포함
![Report Sample](./docs/images/report_preview.png)

### 4. 🔍 지능형 티커 검색

"아이폰"을 검색하면 모기업 "AAPL"를 찾아주는 자동완성 검색 기능을 제공합니다.
![Search Demo](./docs/images/search_preview.png)

---

## ✅ 진행 상황

### Phase 1: 기본 인프라 구축 ✅ 완료

- [x] Streamlit 기반 반응형 웹 UI
- [x] 다크/라이트 모드 지원
- [x] 모듈화된 프로젝트 구조 설계

### Phase 2: 데이터 파이프라인 ✅ 완료

- [x] **Supabase**: 503개 주요 기업 재무 데이터(10-K, 10-Q) DB 구축
- [x] **Finnhub API**: 실시간 주가, 뉴스, 컨센서스 데이터 연동
- [x] **Exchange API**: KST 기준 실시간 원화 환율 연동 완료

### Phase 3: AI 및 RAG 엔진 ✅ 완료

- [x] **Vector Store**: Supabase pgvector 기반 문서 검색
- [x] **GraphRAG**: NetworkX 기반 기업 관계망 분석
- [x] **Performance**: `DataRetriever` 도입으로 병렬 데이터 수집 최적화 완료

### Phase 4: 폴리싱 및 배포 🔄 진행 중

- [x] 챗봇 및 레포트 생성 속도 최적화
- [x] **UI 가독성 향상**: 채팅 폰트 확대, 컨테이너 높이 확장 (800px), 차트 가시성 개선
- [x] **PDF 레포트 고도화**: 다중 차트(캔들스틱, 거래량, 재무) 지원 및 자동 이미지 임베딩
- [x] **차트 기능 확장**: Plotly(웹) 및 Matplotlib(PDF) 기반 다양한 차트 시각화 추가
- [x] **성능 최적화**: 홈 화면 데이터 캐싱 적용 (`st.cache_data`)
- [x] 프로젝트 문서 및 의존성 파일 정리 완료
- [x] 사용자 맞춤형 포트폴리오 관리

---

## 🗂 프로젝트 구조 (요약)

상세 구조는 [STRUCTURE.md](./STRUCTURE.md)를 참조하세요.

```text
SKN22-3rd-4Team/
├── app.py                    # Main Entory Point
├── config/                   # Global Settings
├── src/
│   ├── core/                 # Core Logic (Validator)
│   ├── data/                 # API Clients (Finnhub, Supabase)
│   ├── rag/                  # RAG Engine (Chat, Report, Graph)
│   ├── tools/                # Agent Tools
│   ├── ui/                   # Streamlit Pages & Helpers
│   └── utils/                # Utilities (Charts, PDF)
└── .env                      # API Keys
```

---

## 🔧 설치 및 실행

### 1. 환경 설정

```bash
# 가상환경 생성 (권장)
conda create -n finance_bot python=3.12
conda activate finance_bot

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정 (.env)

```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_KEY=eyJ...
FINNHUB_API_KEY=...
TAVILY_API_KEY=...
```

### 3. 앱 실행
>
> streamlit run app.py

---

## 🌐 API 및 서비스

| 서비스 | 용도 | 상태 |
| :--- | :--- | :--- |
| **Supabase** | 재무제표 DB & Vector Store | ✅ 연동 완료 |
| **Finnhub** | 실시간 주가, 뉴스, 재무 지표 | ✅ 연동 완료 |
| **yfinance** | 주가 추이, 목표주가 (Finnhub fallback) | ✅ 연동 완료 |
| **OpenAI** | LLM (Chat, Report, SQL) | ✅ 연동 완료 |

> **Note**: Finnhub 무료 플랜에서 제한되는 `stock/candle`(주가 추이), `stock/price-target`(목표주가)은 yfinance로 자동 fallback됩니다.

---

## 🛠️ 트러블슈팅 및 기술적 도전

> ### ⚡ Challenge: LLM의 티커(Ticker) 환각(Hallucination) 문제

**문제 상황 (Problem):**
사용자가 "액티비전" 같은 기업명/관련 검색어를 입력했을 때, LLM이 이미 상장 폐지된 티커(`ATVI`)나 엉뚱한 티커를 반환하여 데이터 조회 에러가 발생했습니다.
(참고: 액티비전 블리자드는 마이크로소프트에 인수합병되어 MSFT로 변경되었습니다)

**해결 과정 (Solution):**

1. **DB 기반 자동완성**: 1차적으로 내부 DB(`companies` 테이블)와 매핑된 키워드로 빠르고 정확한 자동완성을 제공했습니다.
2. **지능형 웹 검색 (Agent Fallback)**: DB에 없는 키워드("액티비전" 등)가 입력되면, **Tavily Search API**를 활용한 에이전트가 실시간으로 웹을 검색합니다.
   - *"이 키워드를 만든 회사의 현재 상장 티커는 무엇인가?"*
   - *"혹시 인수합병(M&A)되었는가?"* (예: 액티비전 블리자드(ATVI) -> MSFT)
3. **사용자 피드백 루프**: 시스템이 티커를 대체할 경우, UI에 **"이유(Reason)"**를 명시하여 사용자의 혼란을 방지했습니다.

**결과 (Impact):**

- 정확하지 않은 티커로 인한 크래시 **<1%**
- "오버워치" 같은 게임 이름이나, "Windows" 같은 OS 이름으로도 모기업(MSFT) 분석이 가능한 **유연한 검색 경험** 구현

> ### ⚡ Challenge: finnhub api의 요청 횟수 제한으로 인한 데이터 수집 실패 문제와 데이터 수집 속도 문제

**문제 상황 (Problem):**
Finnhub API는 무료 플랜에서는 일일 요청 횟수에 제한이 있습니다. 이로 인해 여러 기업의 데이터를 동시에 수집하거나, 사용자가 여러 번 요청을 보낼 경우 데이터 수집이 실패하는 문제가 발생했습니다. 또한, Finnhub API의 응답 속도가 느려 데이터 수집 시간이 오래 걸리는 문제가 있었습니다.

**해결 과정 (Solution):**

1. **병렬 수집 최적화**: `DataRetriever` 클래스를 도입하여 여러 기업의 데이터를 동시에 수집할 수 있도록 개선했습니다. 이를 통해 API 요청 횟수를 줄이고 데이터 수집 속도를 높였습니다.
2. **Fallback 메커니즘**: Finnhub API에서 데이터를 가져오지 못할 경우, `yfinance` 라이브러리를 사용하여 대체 데이터를 수집하도록 구현했습니다. 이를 통해 데이터 수집 실패율을 낮추고 사용자 경험을 개선했습니다.

**결과 (Impact):**

- Fallback 메커니즘으로 데이터 수집 실패율 감소
- 데이터 병렬 수집으로 데이터 수집 속도 향상

---

## 📝 라이선스

MIT License

## 후기 (Review)
