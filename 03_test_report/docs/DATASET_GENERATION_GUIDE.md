# 🧪 AI 모델 테스트용 데이터셋 생성 가이드

이 문서는 RAG 모델 성능 평가를 위한 "평가용 데이터셋(Golden Dataset)"을 구축하는 방법을 안내합니다.

---

## 🏗️ 1. 데이터셋 구성 요소

양질의 테스트 데이터셋은 다음 3가지 요소가 포함되어야 합니다.

| 필드 | 설명 | 예시 |
| :---: | :--- | :--- |
| **Question** | 사용자가 물어볼 법한 질문 | "애플의 2023년 매출총이익률은 얼마인가?" |
| **Ground Truth** | 사람이 검증한 정확한 정답 | "애플의 2023년 매출총이익률은 44.1%입니다." |
| **Context** | 정답의 근거가 되는 문서 내용 | (10-K 보고서의 재무제표 주석 부분 발췌) |

---

## 🤖 2. 합성 데이터 생성 (Synthetic Data Generation)

사람이 일일이 질문/답변을 만드는 것은 비효율적입니다. LLM을 사용하여 문서를 읽고 자동으로 질문을 생성하게 하는 것이 좋습니다.

### 추천 도구: [Ragas](https://docs.ragas.io/en/latest/concepts/testset_generation.html)

`Ragas`의 `TestsetGenerator`를 사용하면 문서에서 다양한 유형의 질문을 자동으로 생성할 수 있습니다.

#### ✅ 2.1 설치

```bash
pip install ragas langchain openai
```

#### ✅ 2.2 생성 스크립트 실행

현재 프로젝트의 `src/03_test_report/generate_dataset.py` 스크립트를 사용하여 데이터셋을 생성할 수 있습니다. 이 스크립트는 기업 정보, 재무 데이터, 기업 관계 데이터를 결합하여 더욱 풍부한 컨텍스트를 가진 질문을 생성합니다.

```bash
python 03_test_report/generate_dataset.py
```

---

## 🛠️ 3. 데이터셋 검증 (Human-in-the-loop)

LLM이 생성한 데이터도 100% 완벽하지 않습니다. 생성된 CSV 파일을 열어 다음을 확인하세요.

1. **질문의 명확성**: 질문이 문맥 없이도 이해 가능한가?
    * ❌ "그 회사의 매출은?" (어느 회사인지 모름)
    * ⭕ "애플의 2023년 매출은?"
2. **정답의 정확성**: Ground Truth가 문서 내용과 일치하는가?

---

## 🚀 4. 평가 실행

데이터셋이 준비되면 `TESTING_GUIDE.md`의 **3.1 정량적 평가** 섹션을 참고하여 평가를 실행하세요.

```bash
# 평가 실행
python 03_test_report/evaluate_rag.py
```
