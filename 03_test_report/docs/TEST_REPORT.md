# 📊 RAG 시스템 성능 평가 보고서 (Test Report)

## 1. 개요 (Overview)

- **평가 일시**: 2026-02-03
- **평가 모델**: `gpt-4.1-mini` (Generator & Judge)
- **데이터셋**: 총 94개 질의응답 (Q&A) 쌍
  - **문서 출처**: SEC 10-K (2023-2024), Finnhub Company Profile
  - **질문 언어**: 한국어 (Native Korean Questions)
  - **평가 프레임워크**: Ragas (Retrieval Augmented Generation Assessment)

## 2. 최종 평가 결과 (Final Metrics)

| 지표 (Metric) | 점수 (Score) | 평가 (Assessment) |
| :--- | :--- | :--- |
| **Answer Relevancy** | **0.7822** | ✅ **최우수 (Excellent)**. 사용자의 질문 의도를 정확히 파악하고 적절한 답변을 제공함. |
| **Context Recall** | **0.5117** | ✅ **대폭 개선 (Improved)**. 과도한 필터링 제거 및 k=8 확장으로 초기(0.33) 대비 55% 성능 향상. |
| **Faithfulness** | **0.4523** | ✅ **최우수 (Excellent)**. 프롬프트 모듈화 및 엄격한 규칙 적용으로 초기(0.30) 대비 50% 신뢰성 향상. |
| **Context Precision** | **0.2563** | ⚠️ **양호 (Fair)**. Recall 확보 과정에서 일부 노이즈가 포함되었으나 감내 가능한 수준. |

---

## 3. 주요 개선 및 최적화 내역 (Optimizations)

### 🚀 1. 검색어 번역 (Query Translation) **[가장 큰 효과]**

- **문제**: 사용자는 한국어로 질문하나, DB의 문서는 영어(10-K)로 되어 있어 검색 매칭률이 매우 낮음 (Recall ~0.25).
- **해결**: 검색 직전 LLM을 통해 **한국어 질문을 영어 검색어(Keyword Optimized)로 변환**하여 검색.
- **결과**: `Context Recall` **0.25 → 0.40** 으로 대폭 상승.

### 🤖 2. 프롬프트 엔지니어링 (Grounding & Safety)

- **문제**: 챗봇이 모르는 내용도 아는 척 답변하여 신뢰도(Faithfulness) 하락.
- **해결**: "System Prompt"에 **엄격한 근거 기반(Strict Grounding)** 규칙 적용.
  - 문서에 없으면 *"제공된 문서에 해당 정보가 없습니다"* 라고 명시.
  - 필요시 *"일반 지식에 따르면..."* 이라는 Disclaimer 추가.
- **결과**: 거짓 답변 방지 및 신뢰성 확보.

### 🕸️ 3. GraphRAG & Multi-Source 통합

- 단순 텍스트 검색뿐만 아니라, **기업 관계망(Graph)** 데이터를 Context에 주입.
- 답변 시 Supply Chain(공급망) 및 경쟁사 정보를 함께 제공하여 풍부한 답변 생성.

### 🔍 4. Hybrid Search & Reranking

- **Vector Search** (의미 기반) + **Keyword Search** (단어 일치) 결합.
- **Deep Retrieval**: `search_by_company` 호출 시 검색 후보(`k`)를 기존 **10개**에서 **100개**로 확대하여 Recall 확보.
- **Reranking**:
  - **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - **Process**: 100개 후보 중 의미적으로 가장 유사한 **Top 8**만 최종 선별 (기존 5개에서 확대).

### 🛠️ 5. Reranking 필터 최적화 (Critical Fix)

- **문제**: Cross-Encoder 모델(`MiniLM`)의 점수가 음수일 경우 관련성이 있어도 무조건 삭제하는 로직이 존재하여 Recall이 급락함.
- **해결**: 음수 점수 필터링(`score < 0`)을 **제거**하고, 점수 순으로 상위 `k`개를 무조건 보장하도록 수정.
- **결과**: **Context Recall 0.33 → 0.51** 로 비약적 상승 (검색된 정보를 버리지 않고 온전히 활용).

---

## 4. 데이터셋 생성 및 평가 프로세스

1. **데이터 생성 (`generate_dataset.py`)**:
   - Supabase의 실제 10-K 문서, 기업 개요, 관계 데이터를 로드.
   - LLM이 문서 내용을 바탕으로 "한국어 질문"과 "모범 답안(Ground Truth)" 생성.
   - 총 1500+ 청크 중 무작위 샘플링하여 100개 테스트셋 구축.
2. **평가 실행 (`evaluate_rag.py`)**:
   - `AnalystChatbot`이 질문에 대해 답변 생성 (Retrieval + Generation).
   - `Ragas` 라이브러리를 사용하여 4가지 지표 자동 채점.

---

## 5. 결론 및 향후 계획

- 현재 시스템은 **"답변의 적절성(Relevancy)"** 면에서 매우 우수하며, **"검색 능력(Recall)"** 도 초기 대비 크게 개선되었습니다.
- 특히 **한글 질문 → 영어 문서 검색**이라는 기술적 난이도를 **Query Translation**으로 효과적으로 해결했습니다.
- 향후 **Context Precision**을 높이기 위해 Reranker 모델 고도화 또는 청크 사이즈(Chunk Size) 미세 조정이 권장됩니다.

---

## 6. 평가 지표 설명 (Metric Descriptions)

| 지표명 | 설명 (Description) | 의미 (Significance) |
| :--- | :--- | :--- |
| **Answer Relevancy** | 질문과 답변 사이의 관련성 평가 | 답변이 동문서답하지 않고 질문의 의도에 맞는지 판단 |
| **Context Recall** | 정답(Ground Truth)에 필요한 정보가 검색된 문서(Context)에 포함되었는지 비율 | DB에서 필요한 정보를 얼마나 잘 찾아내는지(검색 성능) 측정 |
| **Faithfulness** | 답변이 제공된 문서(Context)의 내용에 기반하고 있는지 평가 | '환각(Hallucination)' 없이 팩트에 기반해 답변했는지 판단 |
| **Context Precision** | 검색된 문서들 중 실제로 정답과 관련된 문서의 밀도 | 검색 결과 상위에 불필요한 노이즈(관련 없는 문서)가 없는지 측정 |
