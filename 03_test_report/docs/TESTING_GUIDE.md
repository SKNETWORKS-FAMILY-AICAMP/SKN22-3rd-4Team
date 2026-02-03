# 🧪 AI Financial Analyst - 테스트 가이드

이 문서는 프로젝트의 안정성과 AI 모델(RAG)의 성능을 검증하기 위한 테스트 전략 가이드입니다.

---

## 🏗️ 1. 테스트 계층 구조

| 단계 | 테스트 유형 | 설명 | 도구 |
| :---: | :---: | :--- | :---: |
| 1 | **Unit Test** | 개별 함수/모듈(파서, 유틸리티)의 동작 검증 | `pytest` |
| 2 | **Integration Test** | DB, API 등 외부 시스템과의 연동 확인 | `pytest`, 스크립트 |
| 3 | **AI Eval (RAG)** | 챗봇 답변의 정확성, 환각(Hallucination) 여부 평가 | `Ragas`, `LangSmith` |
| 4 | **E2E Test** | 실제 사용자 시나리오(로그인 -> 분석 -> 리포트) 검증 | `Streamlit` (수동) |

---

## ✅ 2. Unit & Integration Test 실행

기본적인 코드 오류를 잡기 위해 `pytest`를 사용합니다.

```bash
# 전체 테스트 실행
pytest

# 특정 파일 테스트
pytest tests/unit/test_chart_utils.py

# 입출력 검증 테스트 (DB 연결 없이)
pytest tests/unit/test_input_validator.py
```

---

## 🤖 3. AI 모델 성능 평가 (RAG Evaluation)

RAG(검색 증강 생성) 시스템은 "정확한 문서를 찾았는지(Retrieval)"와 "질문에 맞는 답을 했는지(Generation)" 두 가지를 평가해야 합니다.

### 3.1 정량적 평가 (자동화 추천)

현재 프로젝트는 **[Ragas](https://github.com/explodinggradients/ragas)** 라이브러리를 사용하여 성능을 측정합니다.

#### 실행 방법

```bash
# RAG 평가 실행 (답변 생성 및 지표 계산)
python 03_test_report/evaluate_rag.py

# 평가 결과 요약 생성
python 03_test_report/generate_report_summary.py
```

지표 설명:

1. **Faithfulness (충실성)**: 답변이 검색된 문서(Context)에 기반했는가? (환각 방지)
2. **Answer Relevance (답변 관련성)**: 질문에 동문서답하지 않았는가?
3. **Context Precision (문맥 정확도)**: 검색된 문서가 실제로 질문과 관련이 있는가?
4. **Context Recall (문맥 재현율)**: 정답에 필요한 정보가 문서에 포함되어 있는가?

---

## 🚪 4. 사용자 경험(UX) 테스트 (Manual)

Streamlit 앱을 실행하고 실제 사용자 시나리오를 점검하세요.

---

## 📝 5. 다음 단계 추천

1. **지표 모니터링**: `generate_report_summary.py`를 통해 출력되는 Ragas 지표가 목표치에 도달하는지 정기적으로 확인하세요.
2. **데이터셋 보강**: `generate_dataset.py`를 통해 더 다양한 샘플을 확보하여 테스트 신뢰도를 높이세요.
